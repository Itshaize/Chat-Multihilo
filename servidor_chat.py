import logging
import socket
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

HOST = "0.0.0.0"  # Escucha en todas las interfaces: permite clientes de la LAN
PUERTO = 8080
MAX_MENSAJE = 1024
MAX_ALIAS = 24


class FormateadorMensajes(ABC):
    """Contrato para el formato de los mensajes del chat."""

    @abstractmethod
    def mensaje(self, alias: str, contenido: str) -> str:
        pass

    @abstractmethod
    def aviso(self, contenido: str) -> str:
        pass


class FormateadorTexto(FormateadorMensajes):
    """Formato de mensajes que reciben los clientes."""

    def mensaje(self, alias: str, contenido: str) -> str:
        return f"[{alias}]: {contenido}"

    def aviso(self, contenido: str) -> str:
        return f"[SISTEMA]: {contenido}"


@dataclass(eq=False)
class ClienteConectado:
    """Representa a un participante; el bloqueo evita envíos simultáneos mezclados."""

    conexion: socket.socket
    direccion: tuple
    alias: str
    bloqueo_envio: threading.Lock = field(default_factory=threading.Lock)

    def enviar(self, mensaje: str) -> None:
        with self.bloqueo_envio:
            self.conexion.sendall((mensaje + "\n").encode("utf-8"))


class RegistroClientes:
    """Administra el conjunto de clientes de forma segura entre hilos."""

    def __init__(self):
        self._clientes = set()
        self._bloqueo = threading.Lock()

    def agregar(self, cliente: ClienteConectado) -> None:
        with self._bloqueo:
            self._clientes.add(cliente)

    def retirar(self, cliente: ClienteConectado) -> bool:
        with self._bloqueo:
            if cliente not in self._clientes:
                return False
            self._clientes.remove(cliente)
            return True

    def listar(self) -> list[ClienteConectado]:
        with self._bloqueo:
            return list(self._clientes)


class ServidorChat:
    """Acepta conexiones TCP y asigna un hilo independiente a cada cliente."""

    def __init__(self, host: str, puerto: int, formateador: FormateadorMensajes):
        self._host = host
        self._puerto = puerto
        self._formateador = formateador
        self._registro = RegistroClientes()

    def _difundir(self, mensaje: str, excluir: ClienteConectado | None = None) -> None:
        """Envía un mensaje a todos los clientes, excepto al emisor si se indica."""
        for destinatario in self._registro.listar():
            if destinatario is excluir:
                continue
            try:
                destinatario.enviar(mensaje)
            except OSError:
                logging.warning("No se pudo enviar a %s (%s)",
                                destinatario.alias, destinatario.direccion)
                # Desbloquea la lectura del hilo del cliente para que se retire.
                try:
                    destinatario.conexion.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def _atender_cliente(self, conexion: socket.socket, direccion: tuple) -> None:
        cliente = None
        logging.info("Conexión recibida desde %s:%s", *direccion)
        try:
            with conexion, conexion.makefile("r", encoding="utf-8") as entrada:
                # Protocolo: la primera línea enviada es el alias del usuario.
                linea_alias = entrada.readline(MAX_ALIAS + 2)
                if not linea_alias or not linea_alias.endswith("\n"):
                    return
                alias = linea_alias.strip()
                if not alias or len(alias) > MAX_ALIAS:
                    return

                cliente = ClienteConectado(conexion, direccion, alias)
                self._registro.agregar(cliente)
                cliente.enviar(self._formateador.aviso(f"Bienvenido, {alias}. Escribe /salir para desconectarte."))
                logging.info("Usuario conectado: %s (%s:%s)", alias, *direccion)
                self._difundir(self._formateador.aviso(f"{alias} se ha unido al chat."), excluir=cliente)

                while True:
                    # Cada mensaje debe terminar con salto de línea (\n).
                    linea = entrada.readline(MAX_MENSAJE + 2)
                    if not linea:
                        break
                    if not linea.endswith("\n") or len(linea.rstrip("\r\n")) > MAX_MENSAJE:
                        cliente.enviar(self._formateador.aviso("Mensaje demasiado largo. Conexión cerrada."))
                        break
                    contenido = linea.strip()
                    if not contenido:
                        continue
                    if contenido.lower() == "/salir":
                        break

                    mensaje = self._formateador.mensaje(alias, contenido)
                    logging.info("%s", mensaje)
                    self._difundir(mensaje, excluir=cliente)
        except (OSError, UnicodeError) as error:
            logging.warning("Error con %s:%s: %s", *direccion, error)
        finally:
            if cliente is not None and self._registro.retirar(cliente):
                self._difundir(self._formateador.aviso(f"{cliente.alias} salió del chat."))
            logging.info("Conexión cerrada: %s:%s", *direccion)

    def iniciar(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((self._host, self._puerto))
            servidor.listen()
            logging.info("Servidor de chat escuchando en %s:%s", self._host, self._puerto)
            try:
                while True:
                    conexion, direccion = servidor.accept()
                    hilo = threading.Thread(
                        target=self._atender_cliente,
                        args=(conexion, direccion),
                        daemon=True
                    )
                    hilo.start()
            except KeyboardInterrupt:
                logging.info("Servidor detenido por el usuario.")


if __name__ == "__main__":
    servidor = ServidorChat(HOST, PUERTO, FormateadorTexto())
    servidor.iniciar()
