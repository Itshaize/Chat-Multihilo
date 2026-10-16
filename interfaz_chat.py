"""Chat LAN en la terminal: Textual y transporte TCP en segundo plano."""
import asyncio
import ipaddress
import queue
from datetime import datetime

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, RichLog, Static

from formato import FormateadorMensajes
from protocolo import COMANDO_SALIR, MAXIMO_ALIAS, MAXIMO_MENSAJE, validar_alias
from red_chat import SesionChat


class InterfazChat(App):
    """Solo el bucle principal modifica widgets; el hilo publica en Queue."""

    TITLE = "Chat LAN"
    SUB_TITLE = "Terminal multiusuario"
    CSS = """
    Screen { background: #111923; color: #d8e1eb; }
    Header { background: #1b2938; }
    #contenido { padding: 0 2; }
    #conexion { height: 5; }
    .campo { width: 1fr; padding-right: 1; height: 5; }
    Label { color: #a7b8ca; height: 1; }
    Input { border: round #40576b; background: #182432; }
    Input:focus { border: round #77b7c9; }
    Button { min-width: 12; margin-left: 1; }
    #conectar { margin-top: 1; }
    #estado { height: 2; color: #a7c8d8; }
    #historial { height: 1fr; min-height: 3; border: round #40576b;
                 background: #141f2b; padding: 0 1; }
    #redactar { height: 3; margin-top: 1; }
    #mensaje { width: 1fr; }
    #controles { height: 3; align-vertical: middle; }
    #sonido { width: 14; border: none; }
    #contador { width: 1fr; padding-top: 1; color: #a7b8ca; }
    Footer { background: #1b2938; }
    .compacto #contenido { padding: 0 1; }
    .compacto #conexion { layout: vertical; height: 9; }
    .compacto .campo { height: 3; width: 100%; }
    .compacto .campo Label { display: none; }
    .compacto #conectar { margin: 0; width: 100%; }
    .compacto #sonido { width: 12; }
    .compacto Button { min-width: 10; }
    """
    BINDINGS = [
        Binding("ctrl+q", "salir", "Salir", priority=True),
        Binding("ctrl+c", "salir", "Salir", show=False, priority=True),
        Binding("ctrl+d", "desconectar", "Desconectar", priority=True),
        Binding("f2", "sonido", "Sonido"),
        Binding("ctrl+l", "leido", "Marcar leído", priority=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sesion = None
        self.conectado = False
        self.cerrando = False
        self.no_leidos = 0
        self.terminal_activa = True
        self.formato = FormateadorMensajes()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="contenido"):
            with Horizontal(id="conexion"):
                with Vertical(classes="campo"):
                    yield Label("Alias")
                    yield Input(placeholder=f"Alias (máximo {MAXIMO_ALIAS})", id="alias")
                with Vertical(classes="campo"):
                    yield Label("IP del servidor")
                    yield Input("127.0.0.1", placeholder="IPv4 del servidor", id="ip")
                yield Button("Conectar", id="conectar", variant="primary")
            yield Static("Desconectado · Introduce tu alias e IP.", id="estado", markup=False)
            yield RichLog(id="historial", wrap=True, markup=False, highlight=False, max_lines=5000)
            with Horizontal(id="redactar"):
                yield Input(placeholder="Escribe un mensaje…", id="mensaje", disabled=True)
                yield Button("Enviar", id="enviar", variant="primary", disabled=True)
            with Horizontal(id="controles"):
                yield Checkbox("Sonido", id="sonido")
                yield Static(f"0/{MAXIMO_MENSAJE}", id="contador")
                yield Button("Desconectar", id="desconectar", disabled=True)
        yield Footer()

    def on_mount(self):
        self.query_one("#historial", RichLog).border_title = "Conversación"
        self.query_one("#alias", Input).focus()
        self.set_interval(0.05, self.procesar_eventos)

    def on_resize(self, evento: events.Resize):
        self.screen.set_class(evento.size.width < 75, "compacto")

    def estado(self, texto):
        self.query_one("#estado", Static).update(Text(texto))

    def agregar(self, texto, etiqueta="aviso"):
        colores = {"aviso": "#91a5bb", "propio": "#7ec5d9", "entrante": "#e0e7ef"}
        # Text evita interpretar alias o mensajes como markup / escapes ANSI.
        seguro = "".join(c for c in texto if c.isprintable() or c == "\t")
        linea = Text(f"{datetime.now():%H:%M}  ", style="#71869c")
        linea.append(seguro, style=colores[etiqueta])
        self.query_one("#historial", RichLog).write(linea)

    @on(Button.Pressed, "#conectar")
    def conectar(self):
        if self.sesion or self.cerrando:
            return
        alias = self.query_one("#alias", Input).value.strip()
        ip = self.query_one("#ip", Input).value.strip()
        if not validar_alias(alias):
            self.estado(f"Alias obligatorio, máximo {MAXIMO_ALIAS} caracteres y una sola línea.")
            return
        try:
            ipaddress.IPv4Address(ip)
        except ipaddress.AddressValueError:
            self.estado("Introduce una IPv4 válida, por ejemplo 192.168.1.10.")
            return
        self.sesion = SesionChat(ip, alias)
        for identificador in ("alias", "ip", "conectar"):
            self.query_one(f"#{identificador}").disabled = True
        self.query_one("#desconectar").disabled = False
        self.estado("Conectando…")
        self.sesion.start()

    @on(Input.Submitted)
    def entrada_confirmada(self, evento: Input.Submitted):
        if evento.input.id == "mensaje":
            self.enviar()
        elif evento.input.id == "alias":
            self.query_one("#ip", Input).focus()
        elif evento.input.id == "ip":
            self.conectar()

    @on(Input.Changed, "#mensaje")
    def contar(self, evento: Input.Changed):
        self.query_one("#contador", Static).update(f"{len(evento.value)}/{MAXIMO_MENSAJE}")

    @on(Button.Pressed, "#enviar")
    def enviar(self):
        if not self.sesion or not self.conectado or self.sesion.detener.is_set():
            return
        entrada = self.query_one("#mensaje", Input)
        mensaje = entrada.value.strip()
        try:
            self.sesion.enviar(mensaje)
        except (ValueError, queue.Full) as error:
            self.estado(str(error) or "Demasiados mensajes pendientes. Espera un momento.")
            return
        entrada.value = ""
        if mensaje.lower() == COMANDO_SALIR:
            self.action_desconectar()

    @on(Button.Pressed, "#desconectar")
    def action_desconectar(self):
        if self.sesion:
            self.sesion.desconectar()
            self.estado("Desconectando…")
            for identificador in ("mensaje", "enviar", "desconectar"):
                self.query_one(f"#{identificador}").disabled = True

    def action_sonido(self):
        self.query_one("#sonido", Checkbox).toggle()

    def action_leido(self):
        self.no_leidos = 0
        self.sub_title = "Terminal multiusuario"
        self.query_one("#historial", RichLog).border_title = "Conversación"

    def on_app_focus(self, evento: events.AppFocus):
        self.terminal_activa = True
        self.action_leido()

    def on_app_blur(self, evento: events.AppBlur):
        self.terminal_activa = False

    def procesar_eventos(self):
        if self.sesion:
            for _ in range(100):
                try:
                    tipo, texto = self.sesion.eventos.get_nowait()
                except queue.Empty:
                    break
                if tipo == "conectado":
                    self.agregar(texto)
                    self.estado(texto)
                    self.conectado = not self.sesion.detener.is_set()
                    if self.conectado:
                        self.query_one("#mensaje").disabled = False
                        self.query_one("#enviar").disabled = False
                        self.query_one("#mensaje", Input).focus()
                elif tipo == "enviado":
                    self.agregar(self.formato.formatear_mensaje(self.sesion.alias, texto), "propio")
                elif tipo == "recibido":
                    self.agregar(texto, "entrante")
                    if not self.terminal_activa:
                        self.no_leidos += 1
                        self.sub_title = f"{self.no_leidos} sin leer"
                    self.query_one("#historial", RichLog).border_title = "Conversación · Nuevo mensaje"
                    self.estado("Nuevo mensaje recibido")
                    if self.query_one("#sonido", Checkbox).value and not self.cerrando:
                        self.bell()
                elif tipo == "desconectado":
                    self.agregar(texto)
                    self.estado(texto)
                    self.conectado = False
                    for identificador in ("mensaje", "enviar", "desconectar"):
                        self.query_one(f"#{identificador}").disabled = True
                    for identificador in ("alias", "ip", "conectar"):
                        self.query_one(f"#{identificador}").disabled = self.cerrando
                    self.sesion = None
                    break
        if self.cerrando and self.sesion is None:
            self.exit()

    def action_salir(self):
        self.cerrando = True
        self.action_desconectar()
        self.query_one("#conectar").disabled = True
        self.estado("Cerrando…")
        if self.sesion is None:
            self.exit()

    async def on_unmount(self):
        # También libera el socket si el framework termina por un error.
        if self.sesion:
            self.sesion.desconectar()
            await asyncio.to_thread(self.sesion.join, 6)


def main():
    InterfazChat().run()


if __name__ == "__main__":
    main()
