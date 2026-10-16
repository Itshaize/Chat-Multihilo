"""Cliente TCP: un hilo envía mientras el hilo principal recibe."""
import socket
import threading

from protocolo import (PUERTO, CODIFICACION, COMANDO_SALIR, MAXIMO_ALIAS,
                       MAXIMO_MENSAJE, validar_alias, validar_mensaje)


class ClienteChat:
    def __init__(self, ip_servidor, puerto, alias):
        self.ip_servidor = ip_servidor
        self.puerto = puerto
        self.alias = alias
        self.conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.activo = threading.Event()

    def conectar(self):
        try:
            self.conexion.settimeout(5)
            self.conexion.connect((self.ip_servidor, self.puerto))
            self.conexion.settimeout(None)
            # Primera línea del protocolo = alias.
            self.conexion.sendall((self.alias + "\n").encode(CODIFICACION))
            self.activo.set()
            print(f"\nConectado como {self.alias}")
            print(f"Escribe {COMANDO_SALIR} para desconectarte.\n")
            threading.Thread(target=self.enviar_mensajes, daemon=True).start()
            self.recibir_mensajes()
        except (OSError, KeyboardInterrupt) as error:
            print(f"\nError de conexión: {error}")
        finally:
            self.desconectar()

    def recibir_mensajes(self):
        try:
            with self.conexion.makefile("r", encoding=CODIFICACION, errors="replace") as entrada:
                while self.activo.is_set():
                    linea = entrada.readline()
                    if not linea:
                        if self.activo.is_set():
                            print("\nEl servidor se desconectó.")
                        break
                    print(f"\n{linea.rstrip()}")
        except OSError as error:
            if self.activo.is_set():
                print(f"\nError al recibir: {error}")
        finally:
            self.activo.clear()

    def enviar_mensajes(self):
        try:
            while self.activo.is_set():
                mensaje = input("> ").strip()
                if not self.activo.is_set() or mensaje.lower() == COMANDO_SALIR:
                    break
                if not mensaje:
                    continue
                if not validar_mensaje(mensaje):
                    print(f"El mensaje debe tener entre 1 y {MAXIMO_MENSAJE} caracteres.")
                    continue
                self.conexion.sendall((mensaje + "\n").encode(CODIFICACION))
        except (KeyboardInterrupt, EOFError):
            print("\nSalida solicitada.")
        except OSError as error:
            if self.activo.is_set():
                print(f"\nError al enviar: {error}")
        finally:
            self.activo.clear()
            try:
                self.conexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def desconectar(self):
        self.activo.clear()
        try:
            self.conexion.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.conexion.close()
        print("Cliente finalizado.")


if __name__ == "__main__":
    print("=== CHAT MULTIUSUARIO LAN ===")
    alias = input("Ingresa tu alias: ").strip()
    while not validar_alias(alias):
        alias = input(f"Alias obligatorio (máximo {MAXIMO_ALIAS} caracteres): ").strip()
    ip = input("IP del servidor [127.0.0.1]: ").strip() or "127.0.0.1"
    ClienteChat(ip, PUERTO, alias).conectar()
