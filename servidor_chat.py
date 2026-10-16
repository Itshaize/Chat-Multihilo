"""Servidor de chat TCP multihilo y difusión a clientes activos."""
import logging
import socket
import threading
from dataclasses import dataclass, field

from protocolo import (IP_SERVIDOR, PUERTO, CODIFICACION, COMANDO_SALIR,
                       MAXIMO_ALIAS, MAXIMO_MENSAJE, validar_alias, validar_mensaje)
from formato import FormateadorMensajes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@dataclass(eq=False)
class ClienteConectado:
    conexion: socket.socket
    direccion: tuple
    alias: str
    bloqueo_envio: threading.Lock = field(default_factory=threading.Lock)

    def enviar(self, mensaje: str) -> None:
        with self.bloqueo_envio:
            self.conexion.sendall((mensaje + "\n").encode(CODIFICACION))


class RegistroClientes:
    """Registro de clientes protegido para operaciones concurrentes."""
    def __init__(self):
        self._clientes = set()
        self._bloqueo = threading.Lock()

    def agregar(self, cliente):
        with self._bloqueo:
            self._clientes.add(cliente)

    def retirar(self, cliente):
        with self._bloqueo:
            if cliente not in self._clientes:
                return False
            self._clientes.remove(cliente)
            return True

    def listar(self):
        with self._bloqueo:
            return list(self._clientes)


class ServidorChat:
    def __init__(self, host=IP_SERVIDOR, puerto=PUERTO, formateador=None):
        self._host = host
        self._puerto = puerto
        self._formateador = formateador or FormateadorMensajes()
        self._registro = RegistroClientes()

    def _difundir(self, mensaje, excluir=None):
        for destinatario in self._registro.listar():
            if destinatario is excluir:
                continue
            try:
                destinatario.enviar(mensaje)
            except OSError:
                logging.warning("Error al enviar a %s (%s)", destinatario.alias, destinatario.direccion)
                try:
                    destinatario.conexion.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def _atender_cliente(self, conexion, direccion):
        cliente = None
        logging.info("Conexión recibida desde %s:%s", *direccion)
        try:
            with conexion, conexion.makefile("r", encoding=CODIFICACION) as entrada:
                linea_alias = entrada.readline(MAXIMO_ALIAS + 2)
                if not linea_alias.endswith("\n"):
                    return
                alias = linea_alias.rstrip("\r\n")
                if not validar_alias(alias):
                    return

                cliente = ClienteConectado(conexion, direccion, alias)
                cliente.enviar(f"[SISTEMA]: Bienvenido, {alias}. Escribe {COMANDO_SALIR} para salir.")
                self._registro.agregar(cliente)
                logging.info("Usuario conectado: %s (%s:%s)", alias, *direccion)
                self._difundir(self._formateador.formatear_conexion(alias), excluir=cliente)

                while True:
                    linea = entrada.readline(MAXIMO_MENSAJE + 2)
                    if not linea:
                        break
                    if not linea.endswith("\n") or len(linea.rstrip("\r\n")) > MAXIMO_MENSAJE:
                        cliente.enviar("[SISTEMA]: Mensaje demasiado largo. Conexión cerrada.")
                        break
                    contenido = linea.rstrip("\r\n")
                    if not contenido.strip():
                        continue
                    if contenido.strip().lower() == COMANDO_SALIR:
                        break
                    if not validar_mensaje(contenido):
                        continue
                    mensaje = self._formateador.formatear_mensaje(alias, contenido)
                    logging.info("%s", mensaje)
                    self._difundir(mensaje, excluir=cliente)
        except (OSError, UnicodeError, ValueError) as error:
            logging.warning("Error con %s:%s: %s", *direccion, error)
        finally:
            if cliente is not None and self._registro.retirar(cliente):
                self._difundir(self._formateador.formatear_desconexion(cliente.alias))
            logging.info("Conexión cerrada: %s:%s", *direccion)

    def iniciar(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((self._host, self._puerto))
            servidor.listen()
            logging.info("Servidor escuchando en %s:%s", self._host, self._puerto)
            try:
                while True:
                    conexion, direccion = servidor.accept()
                    threading.Thread(target=self._atender_cliente,
                                     args=(conexion, direccion), daemon=True).start()
            except KeyboardInterrupt:
                logging.info("Servidor detenido por el usuario.")


if __name__ == "__main__":
    ServidorChat().iniciar()
