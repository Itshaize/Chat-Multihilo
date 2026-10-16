"""Cliente gráfico LAN. Los hilos de red nunca acceden a Tkinter."""
import ipaddress
import queue
import select
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import font, ttk

from formato import FormateadorMensajes
from protocolo import (PUERTO, CODIFICACION, COMANDO_SALIR, MAXIMO_ALIAS,
                       MAXIMO_MENSAJE, validar_alias, validar_mensaje)


class SesionChat(threading.Thread):
    """Un hilo por sesión; eventos (tipo, texto) y salida FIFO independientes.

    El socket pertenece exclusivamente a este hilo. El cierre se solicita con
    un Event; select limita la espera sin bloquear el bucle gráfico.
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
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conexion:
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


class InterfazChat:
    def __init__(self, raiz):
        self.raiz = raiz
        self.sesion = None
        self.cerrando = False
        self.no_leidos = 0
        self.formato = FormateadorMensajes()
        raiz.title("Chat LAN")
        raiz.geometry("760x600")
        raiz.minsize(560, 440)
        raiz.configure(background="#eef2f6")
        estilo = ttk.Style(raiz)
        estilo.theme_use("clam")
        familia = font.nametofont("TkDefaultFont").actual("family")
        estilo.configure("TFrame", background="#eef2f6")
        estilo.configure("TLabel", background="#eef2f6", foreground="#243447", font=(familia, 10))
        estilo.configure("TButton", padding=(12, 7))
        estilo.configure("Title.TLabel", font=(familia, 20, "bold"))
        panel = ttk.Frame(raiz, padding=20)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Chat LAN", style="Title.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Conversaciones en tu red local").pack(anchor="w", pady=(0, 16))
        acceso = ttk.Frame(panel)
        acceso.pack(fill="x")
        self.alias = tk.StringVar()
        self.ip = tk.StringVar(value="127.0.0.1")
        self.campos = []
        for columna, (texto, variable, ancho) in enumerate((("Alias", self.alias, 22), ("IP del servidor", self.ip, 18))):
            ttk.Label(acceso, text=texto).grid(row=0, column=columna, sticky="w")
            campo = ttk.Entry(acceso, textvariable=variable, width=ancho)
            campo.grid(row=1, column=columna, sticky="ew", padx=(0, 10))
            self.campos.append(campo)
        acceso.columnconfigure(1, weight=1)
        self.conectar_boton = ttk.Button(acceso, text="Conectar", command=self.conectar)
        self.conectar_boton.grid(row=1, column=2)
        self.estado = tk.StringVar(value="Desconectado · Introduce tu alias e IP para comenzar.")
        ttk.Label(panel, textvariable=self.estado, wraplength=680).pack(anchor="w", pady=12)
        historial_panel = ttk.Frame(panel)
        historial_panel.pack(fill="both", expand=True)
        self.historial = tk.Text(historial_panel, wrap="word", state="disabled", font=(familia, 11),
                                 background="#ffffff", foreground="#243447", relief="flat", padx=14, pady=12)
        barra = ttk.Scrollbar(historial_panel, command=self.historial.yview)
        self.historial.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.historial.pack(fill="both", expand=True)
        for etiqueta, color in (("propio", "#235e91"), ("entrante", "#243447"), ("aviso", "#64748b")):
            self.historial.tag_configure(etiqueta, foreground=color, spacing3=10)
        self.mensaje = tk.StringVar()
        self.entrada = ttk.Entry(panel, textvariable=self.mensaje, state="disabled")
        self.entrada.pack(fill="x", pady=(14, 6))
        self.entrada.bind("<Return>", lambda evento: self.enviar())
        controles = ttk.Frame(panel)
        controles.pack(fill="x")
        self.enviar_boton = ttk.Button(controles, text="Enviar", command=self.enviar, state="disabled")
        self.enviar_boton.pack(side="right")
        self.desconectar_boton = ttk.Button(controles, text="Desconectar", command=self.desconectar, state="disabled")
        self.desconectar_boton.pack(side="right", padx=8)
        self.sonido = tk.BooleanVar(value=False)
        ttk.Checkbutton(controles, text="Sonido", variable=self.sonido).pack(side="left")
        self.contador = tk.StringVar(value=f"0/{MAXIMO_MENSAJE}")
        ttk.Label(controles, textvariable=self.contador).pack(side="left", padx=8)
        self.mensaje.trace_add("write", lambda *_: self.contador.set(f"{len(self.mensaje.get())}/{MAXIMO_MENSAJE}"))
        raiz.bind("<FocusIn>", self.al_enfocar)
        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.campos[0].focus_set()
        raiz.after(50, self.procesar_eventos)

    def agregar(self, texto, etiqueta="aviso"):
        self.historial.configure(state="normal")
        self.historial.insert("end", f"{datetime.now():%H:%M}  {texto}\n", etiqueta)
        self.historial.configure(state="disabled")
        self.historial.see("end")

    def conectar(self):
        if self.sesion or self.cerrando:
            return
        alias, ip = self.alias.get().strip(), self.ip.get().strip()
        if not validar_alias(alias):
            self.estado.set(f"Alias obligatorio, máximo {MAXIMO_ALIAS} caracteres y una sola línea.")
            return
        try:
            ipaddress.IPv4Address(ip)
        except ipaddress.AddressValueError:
            self.estado.set("Introduce una dirección IPv4 válida, por ejemplo 192.168.1.10.")
            return
        self.sesion = SesionChat(ip, alias)
        self.conectar_boton.configure(state="disabled")
        for campo in self.campos:
            campo.configure(state="disabled")
        self.desconectar_boton.configure(state="normal")
        self.estado.set("Conectando…")
        self.sesion.start()

    def enviar(self):
        if not self.sesion or str(self.entrada["state"]) == "disabled":
            return
        mensaje = self.mensaje.get().strip()
        try:
            self.sesion.enviar(mensaje)
        except (ValueError, queue.Full) as error:
            self.estado.set(str(error) or "Hay demasiados mensajes pendientes. Espera un momento.")
            return
        self.mensaje.set("")
        if mensaje.lower() == COMANDO_SALIR:
            self.desconectar()

    def desconectar(self):
        if self.sesion:
            self.sesion.desconectar()
            self.estado.set("Desconectando…")
            for widget in (self.entrada, self.enviar_boton, self.desconectar_boton):
                widget.configure(state="disabled")

    def al_enfocar(self, evento=None):
        self.no_leidos = 0
        self.raiz.title("Chat LAN")

    def procesar_eventos(self):
        if self.sesion:
            for _ in range(100):
                try:
                    tipo, texto = self.sesion.eventos.get_nowait()
                except queue.Empty:
                    break
                if tipo == "conectado":
                    self.agregar(texto)
                    self.estado.set(texto)
                    if not self.sesion.detener.is_set():
                        self.entrada.configure(state="normal")
                        self.enviar_boton.configure(state="normal")
                        self.entrada.focus_set()
                elif tipo == "enviado":
                    self.agregar(self.formato.formatear_mensaje(self.sesion.alias, texto), "propio")
                elif tipo == "recibido":
                    self.agregar(texto, "entrante")
                    if self.raiz.focus_displayof() is None:
                        self.no_leidos += 1
                        self.raiz.title(f"({self.no_leidos}) Chat LAN · Mensajes nuevos")
                    self.estado.set("Nuevo mensaje recibido")
                    if self.sonido.get() and not self.cerrando:
                        self.raiz.bell()
                elif tipo == "desconectado":
                    self.agregar(texto)
                    self.estado.set(texto)
                    for widget in (self.entrada, self.enviar_boton, self.desconectar_boton):
                        widget.configure(state="disabled")
                    for campo in self.campos:
                        campo.configure(state="normal")
                    self.conectar_boton.configure(state="normal")
                    self.sesion = None
                    break
        if self.cerrando and self.sesion is None:
            self.raiz.destroy()
            return
        self.raiz.after(50, self.procesar_eventos)

    def cerrar(self):
        self.cerrando = True
        self.desconectar()
        self.conectar_boton.configure(state="disabled")
        self.estado.set("Cerrando…")


def main():
    raiz = tk.Tk()
    InterfazChat(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
