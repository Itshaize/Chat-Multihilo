"""Servidor de chat: una conexión y un hilo por compañero."""
import socket
import threading


class ClientHandler:
    def __init__(self, conexion, servidor):
        self.conexion = conexion
        self.servidor = servidor

    def process(self):
        nombre = ""
        registrado = False
        try:
            with self.conexion, self.conexion.makefile("r", encoding="utf-8") as entrada:
                # Primera línea: nombre. Después: un mensaje por línea.
                linea = entrada.readline(82)
                nombre = linea.strip()
                if not linea.endswith("\n") or not nombre or len(nombre) > 80:
                    return
                with self.servidor.bloqueo:
                    self.conexion.sendall(f"Bienvenido, {nombre}.\n".encode("utf-8"))
                    self.servidor.clientes.append(self.conexion)
                    registrado = True
                self.servidor.broadcast(f"--- {nombre} entró al chat ---")
                while True:
                    linea = entrada.readline(4002)
                    if not linea or not linea.endswith("\n"):
                        break
                    mensaje = linea.strip()
                    if mensaje.lower() == "/salir":
                        break
                    if mensaje and len(mensaje) <= 4000:
                        self.servidor.broadcast(f"[{nombre}]: {mensaje}")
        except (OSError, UnicodeError):
            pass
        finally:
            if registrado:
                with self.servidor.bloqueo:
                    self.servidor.clientes.remove(self.conexion)
                self.servidor.broadcast(f"--- {nombre} salió del chat ---")


class ThreadedSocketServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.clientes = []
        self.bloqueo = threading.Lock()

    def broadcast(self, mensaje):
        # Un solo hilo envía a la vez para no mezclar los mensajes.
        print(mensaje, flush=True)
        with self.bloqueo:
            for conexion in self.clientes:
                try:
                    conexion.sendall((mensaje + "\n").encode("utf-8"))
                except OSError:
                    try:
                        conexion.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((self.host, self.port))
            servidor.listen()
            print(f"Chat iniciado en {self.host}:{self.port}", flush=True)
            print("Ctrl+C para detener.", flush=True)
            try:
                while True:
                    conexion, direccion = servidor.accept()
                    handler = ClientHandler(conexion, self)
                    threading.Thread(target=handler.process, daemon=True).start()
            finally:
                with self.bloqueo:
                    for conexion in self.clientes:
                        try:
                            conexion.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass


if __name__ == "__main__":
    try:
        ThreadedSocketServer().start()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    except OSError as error:
        print(f"No se pudo iniciar el servidor: {error}")
