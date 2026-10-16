"""Chat básico: el teclado envía y un hilo recibe a los compañeros."""
import socket
import threading


class SocketClient:
    def __init__(self, host, port=8080):
        self.host = host
        self.port = port
        self.conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.activo = threading.Event()

    def connect(self, nombre):
        self.conexion.settimeout(5)
        self.conexion.connect((self.host, self.port))
        self.conexion.settimeout(None)
        self.conexion.sendall((nombre + "\n").encode("utf-8"))
        self.activo.set()

    def send_message(self, mensaje):
        self.conexion.sendall((mensaje + "\n").encode("utf-8"))

    def receive_messages(self):
        try:
            with self.conexion.makefile("r", encoding="utf-8") as entrada:
                for linea in entrada:
                    print("\n" + linea.rstrip(), flush=True)
        except (OSError, UnicodeError):
            pass
        finally:
            if self.activo.is_set():
                print("\nEl servidor se desconectó. Pulsa Enter para salir.", flush=True)
            self.activo.clear()

    def close(self):
        self.activo.clear()
        try:
            self.conexion.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.conexion.close()


def main():
    print("------------------------------")
    print("    BIENVENIDO AL CHAT")
    print("------------------------------")
    client = None
    receptor = None
    try:
        nombre = input("Tu nombre: ").strip() or "Usuario"
        while len(nombre) > 80:
            nombre = input("Nombre de hasta 80 caracteres: ").strip() or "Usuario"
        ip = input("IP del servidor [127.0.0.1]: ").strip() or "127.0.0.1"
        client = SocketClient(ip, 8080)
        client.connect(nombre)
        print("------------------------------")
        print("Escribe un mensaje y pulsa Enter.")
        print("Escribe /salir para terminar.")
        print("------------------------------")
        # Recibe aunque el usuario esté esperando para escribir.
        receptor = threading.Thread(target=client.receive_messages, daemon=True)
        receptor.start()
        while client.activo.is_set():
            mensaje = input("> ").strip()
            if not client.activo.is_set():
                break
            if mensaje.lower() == "/salir":
                client.send_message("/salir")
                break
            if len(mensaje) > 4000:
                print("Máximo 4000 caracteres por mensaje.")
            elif mensaje:
                client.send_message(mensaje)
    except OSError as error:
        print(f"Error de conexión: {error}. Revisa la IP y que el servidor esté encendido.")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        if client:
            client.close()
        if receptor:
            receptor.join(2)
    print("Hasta luego.")


if __name__ == "__main__":
    main()
