import socket
import threading


class ClienteChat:
    def __init__(self, ip_servidor, puerto, alias):
        self.ip_servidor = ip_servidor
        self.puerto = puerto
        self.alias = alias
        self.conexion = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        )
        self.activo = threading.Event()

    def conectar(self):
        try:
            self.conexion.settimeout(5)
            self.conexion.connect(
                (self.ip_servidor, self.puerto)
            )
            self.conexion.settimeout(None)

            self.activo.set()

            print(f"\nConectado como {self.alias}")
            print("Escribe /salir para desconectarte.\n")

            hilo_recepcion = threading.Thread(
                target=self.recibir_mensajes,
                daemon=True
            )
            hilo_recepcion.start()

            self.enviar_mensajes()

        except OSError as error:
            print(f"Error de conexión: {error}")

        finally:
            self.desconectar()

    def recibir_mensajes(self):
        try:
            while self.activo.is_set():
                datos = self.conexion.recv(4096)

                if not datos:
                    print("\nEl servidor se desconectó.")
                    break

                mensaje = datos.decode(
                    "utf-8", errors="replace"
                )
                print(f"\n{mensaje.rstrip()}")

        except OSError as error:
            if self.activo.is_set():
                print(f"\nError al recibir: {error}")

        finally:
            self.activo.clear()

    def enviar_mensajes(self):
        try:
            while self.activo.is_set():
                mensaje = input("> ").strip()

                if mensaje.lower() == "/salir":
                    break

                if not mensaje:
                    continue

                texto = f"[{self.alias}]: {mensaje}\n"
                self.conexion.sendall(
                    texto.encode("utf-8")
                )

        except (KeyboardInterrupt, EOFError):
            print("\nSalida solicitada.")

        except OSError as error:
            print(f"\nError al enviar: {error}")

    def desconectar(self):
        self.activo.clear()

        try:
            self.conexion.shutdown(
                socket.SHUT_RDWR
            )
        except OSError:
            pass

        self.conexion.close()
        print("Cliente finalizado.")


if __name__ == "__main__":
    print("=== CHAT MULTIUSUARIO ===")

    alias = input("Ingresa tu alias: ").strip()

    while not alias:
        alias = input("El alias es obligatorio: ").strip()

    ip = input(
        "IP del servidor [127.0.0.1]: "
    ).strip() or "127.0.0.1"

    cliente = ClienteChat(ip, 8080, alias)
    cliente.conectar()