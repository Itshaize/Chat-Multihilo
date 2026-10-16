"""Transporte TCP del chat LAN, independiente de la interfaz."""
import queue
import select
import socket
from socket import socket as crear_socket
import threading

from protocolo import (PUERTO, CODIFICACION, COMANDO_SALIR,
                       MAXIMO_MENSAJE, validar_mensaje)


class SesionChat(threading.Thread):
    """Un hilo por sesión; eventos (tipo, texto) y salida FIFO independientes.

    El socket pertenece exclusivamente a este hilo. El cierre se solicita con
    un Event; select limita la espera sin bloquear el bucle de la interfaz.
    """
    def __init__(self, ip, alias, puerto=PUERTO):
        super().__init__(daemon=True)
        self.ip, self.alias, self.puerto = ip, alias, puerto
        self.eventos = queue.Queue()
        self.salientes = queue.Queue(maxsize=100)
        self.detener = threading.Event()

    def enviar(self, mensaje):
        if not validar_mensaje(mensaje):
            raise ValueError(f"Mensaje obligatorio, de hasta {MAXIMO_MENSAJE} caracteres y una sola línea.")
        if mensaje.strip().lower() == COMANDO_SALIR:
            self.desconectar()
        else:
            self.salientes.put_nowait(mensaje)

    def desconectar(self):
        self.detener.set()

    def run(self):
        motivo = "Desconectado."
        try:
            with crear_socket(socket.AF_INET, socket.SOCK_STREAM) as conexion:
                conexion.settimeout(5)
                conexion.connect((self.ip, self.puerto))
                conexion.settimeout(1)
                if self.detener.is_set():
                    return
                conexion.sendall((self.alias + "\n").encode(CODIFICACION))
                self.eventos.put(("conectado", f"Conectado como {self.alias} a {self.ip}:{self.puerto}."))
                pendiente = b""
                while not self.detener.is_set():
                    # Limitar el lote permite atender recepción y cancelación.
                    for _ in range(10):
                        if self.detener.is_set():
                            break
                        try:
                            mensaje = self.salientes.get_nowait()
                        except queue.Empty:
                            break
                        conexion.sendall((mensaje + "\n").encode(CODIFICACION))
                        self.eventos.put(("enviado", mensaje))
                    if not select.select([conexion], [], [], 0.1)[0]:
                        continue
                    datos = conexion.recv(4096)
                    if not datos:
                        motivo = "El servidor cerró la conexión."
                        break
                    pendiente += datos
                    while b"\n" in pendiente:
                        linea, pendiente = pendiente.split(b"\n", 1)
                        self.eventos.put(("recibido", linea.rstrip(b"\r").decode(CODIFICACION)))
                    if len(pendiente) > 16384:
                        raise ValueError("El servidor envió una línea demasiado larga.")
                if self.detener.is_set():
                    try:
                        conexion.sendall((COMANDO_SALIR + "\n").encode(CODIFICACION))
                        conexion.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
        except (OSError, UnicodeError, ValueError) as error:
            if not self.detener.is_set():
                motivo = f"Error de red: {error}"
        finally:
            self.eventos.put(("desconectado", motivo))

