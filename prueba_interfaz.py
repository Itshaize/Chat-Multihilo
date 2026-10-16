"""Integración con sockets reales y comprobaciones del bucle TUI."""
import socket
import threading
import time
import asyncio
import unittest
from unittest.mock import MagicMock, patch
from textual import events
from textual.widgets import Checkbox, Input, RichLog

from interfaz_chat import InterfazChat, SesionChat
from protocolo import CODIFICACION, MAXIMO_ALIAS, MAXIMO_MENSAJE
from servidor_chat import ServidorChat


class PruebasIntegracion(unittest.TestCase):
    def setUp(self):
        self.servidor = ServidorChat()
        self.oyente = socket.socket()
        self.oyente.bind(("127.0.0.1", 0))
        self.oyente.listen()
        self.puerto = self.oyente.getsockname()[1]
        self.recursos, self.hilos = [], []

    def aceptar(self):
        conexion, direccion = self.oyente.accept()
        hilo = threading.Thread(target=self.servidor._atender_cliente,
                                args=(conexion, direccion), daemon=True)
        hilo.start()
        self.hilos.append(hilo)

    def cliente(self, alias):
        conexion = socket.create_connection(("127.0.0.1", self.puerto), timeout=2)
        self.recursos.append(conexion)
        self.aceptar()
        entrada = conexion.makefile("r", encoding=CODIFICACION)
        self.recursos.append(entrada)
        conexion.sendall((alias + "\n").encode(CODIFICACION))
        return conexion, entrada

    def evento(self, sesion, tipo):
        limite = time.monotonic() + 7
        while time.monotonic() < limite:
            evento, texto = sesion.eventos.get(timeout=max(0.01, limite - time.monotonic()))
            if evento == tipo:
                return texto
        self.fail(f"No llegó el evento {tipo}")

    def tearDown(self):
        for recurso in self.recursos:
            if isinstance(recurso, socket.socket):
                try:
                    recurso.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        for recurso in reversed(self.recursos):
            recurso.close()
        self.oyente.close()
        for hilo in self.hilos:
            hilo.join(3)
            self.assertFalse(hilo.is_alive())

    def test_difusion_utf8_fragmentada_limite_y_salir(self):
        _, entrada_ana = self.cliente("Ana")
        self.assertIn("Bienvenido, Ana", entrada_ana.readline())
        bob, entrada_bob = self.cliente("B" * MAXIMO_ALIAS)
        self.assertIn("Bienvenido", entrada_bob.readline())
        self.assertIn("se ha conectado", entrada_ana.readline())
        datos = ("¡Hola!\n" + "ñ" * MAXIMO_MENSAJE + "\n").encode(CODIFICACION)
        bob.sendall(datos[:1])
        bob.sendall(datos[1:])
        self.assertEqual(entrada_ana.readline().rstrip(), f"[{'B' * MAXIMO_ALIAS}]: ¡Hola!")
        self.assertEqual(entrada_ana.readline().rstrip(), f"[{'B' * MAXIMO_ALIAS}]: " + "ñ" * MAXIMO_MENSAJE)
        bob.sendall(b"/salir\n")
        self.assertEqual(entrada_bob.readline(), "")
        self.assertIn("se ha desconectado", entrada_ana.readline())

    def test_alias_invalido_y_mensaje_demasiado_largo(self):
        _, entrada = self.cliente("a" * (MAXIMO_ALIAS + 1))
        self.assertEqual(entrada.readline(), "")
        conexion, entrada = self.cliente("Ana")
        self.assertIn("Bienvenido", entrada.readline())
        conexion.sendall(("x" * (MAXIMO_MENSAJE + 1) + "\n").encode(CODIFICACION))
        self.assertIn("demasiado largo", entrada.readline())
        self.assertEqual(entrada.readline(), "")

    def test_sesion_grafica_y_cliente_tcp(self):
        conexion, entrada = self.cliente("Consola")
        self.assertIn("Bienvenido", entrada.readline())
        sesion = SesionChat("127.0.0.1", "Gráfica", self.puerto)
        sesion.start()
        self.aceptar()
        try:
            self.evento(sesion, "conectado")
            self.assertIn("Bienvenido", self.evento(sesion, "recibido"))
            self.assertIn("se ha conectado", entrada.readline())
            sesion.enviar("Hola ñ")
            self.assertEqual(entrada.readline(), "[Gráfica]: Hola ñ\n")
            self.assertEqual(self.evento(sesion, "enviado"), "Hola ñ")
            conexion.sendall(b"Respuesta\n")
            self.assertEqual(self.evento(sesion, "recibido"), "[Consola]: Respuesta")
            sesion.enviar("/SALIR")
            self.evento(sesion, "desconectado")
            self.assertIn("se ha desconectado", entrada.readline())
        finally:
            sesion.desconectar()
            sesion.join(3)
        self.assertFalse(sesion.is_alive())

    def test_cierre_repentino_del_servidor(self):
        sesion = SesionChat("127.0.0.1", "Ana", self.puerto)
        sesion.start()
        conexion, _ = self.oyente.accept()
        try:
            self.evento(sesion, "conectado")
            conexion.shutdown(socket.SHUT_RDWR)
        finally:
            conexion.close()
        motivo = self.evento(sesion, "desconectado")
        # El sistema puede producir EOF o un reset TCP; su texto depende
        # del idioma del SO. Ambos deben terminar el hilo y avisar a Tk.
        self.assertTrue(motivo == "El servidor cerró la conexión."
                        or motivo.startswith("Error de red:"), motivo)
        sesion.join(3)
        self.assertFalse(sesion.is_alive())

    def test_conexion_rechazada(self):
        self.oyente.close()
        sesion = SesionChat("127.0.0.1", "Ana", self.puerto)
        sesion.start()
        self.assertIn("Error de red", self.evento(sesion, "desconectado"))
        sesion.join(3)

    def test_validacion_salida(self):
        sesion = SesionChat("127.0.0.1", "Ana", self.puerto)
        for mensaje in ("", "a\nb", "a\rb", "x" * (MAXIMO_MENSAJE + 1)):
            with self.assertRaises(ValueError):
                sesion.enviar(mensaje)


class PruebasTUI(unittest.IsolatedAsyncioTestCase):
    async def test_validacion_teclado_y_terminal_compacta(self):
        app = InterfazChat()
        async with app.run_test(size=(64, 28)) as piloto:
            await piloto.click("#conectar")
            self.assertIsNone(app.sesion)
            self.assertIn("Alias obligatorio", str(app.query_one("#estado").render()))
            await piloto.click("#alias")
            await piloto.press("A", "n", "a", "enter")
            self.assertEqual(app.focused.id, "ip")
            app.query_one("#ip", Input).value = "inválida"
            await piloto.press("enter")
            self.assertIsNone(app.sesion)
            self.assertIn("IPv4 válida", str(app.query_one("#estado").render()))
            await piloto.press("f2")
            self.assertTrue(app.query_one("#sonido", Checkbox).value)
            self.assertTrue(app.screen.has_class("compacto"))

    async def test_eventos_hilo_principal_no_leidos_y_markup_literal(self):
        app = InterfazChat()
        async with app.run_test() as piloto:
            sesion = SesionChat("127.0.0.1", "Ana")
            app.sesion = sesion
            principal, agregar = threading.get_ident(), app.agregar
            def comprobar(*args):
                self.assertEqual(threading.get_ident(), principal)
                agregar(*args)
            app.agregar = comprobar
            app.on_app_blur(events.AppBlur())
            def publicar():
                sesion.eventos.put(("recibido", "[Bob]: [bold]Hola[/bold]\x1b"))
                sesion.eventos.put(("enviado", "Respuesta"))
            hilo = threading.Thread(target=publicar)
            hilo.start()
            hilo.join()
            await piloto.pause(0.15)
            self.assertEqual(app.no_leidos, 1)
            self.assertEqual(app.sub_title, "1 sin leer")
            historial = app.query_one("#historial", RichLog)
            lineas = "\n".join(linea.text for linea in historial.lines)
            self.assertIn("[bold]Hola[/bold]", lineas)
            self.assertNotIn("\x1b", lineas)
            self.assertIn("[Ana]: Respuesta", lineas)
            app.on_app_focus(events.AppFocus())
            self.assertEqual(app.no_leidos, 0)
            sesion.eventos.put(("desconectado", "Conexión cerrada"))
            await piloto.pause(0.15)
            self.assertIsNone(app.sesion)
            self.assertFalse(app.query_one("#conectar").disabled)

    async def test_cerrar_durante_conexion_mantiene_bucle_activo(self):
        inicio, liberar = threading.Event(), threading.Event()
        conexion = MagicMock()
        conexion.__enter__.return_value = conexion
        def conectar_lento(*args):
            inicio.set()
            liberar.wait(3)
        conexion.connect.side_effect = conectar_lento
        app = InterfazChat()
        with patch("red_chat.crear_socket", return_value=conexion):
            async with app.run_test() as piloto:
                app.query_one("#alias", Input).value = "Ana"
                app.conectar()
                sesion = app.sesion
                try:
                    self.assertTrue(await asyncio.to_thread(inicio.wait, 1))
                    await piloto.press("ctrl+q")
                    self.assertTrue(app.cerrando)
                    self.assertTrue(sesion.is_alive())
                    atendido = []
                    app.call_later(lambda: atendido.append(True))
                    await piloto.pause(0.05)
                    self.assertEqual(atendido, [True])
                finally:
                    liberar.set()
                    await asyncio.to_thread(sesion.join, 3)
                await piloto.pause(0.15)
                self.assertFalse(sesion.is_alive())
            conexion.__exit__.assert_called_once()

    async def test_chat_tui_servidor_real_y_reconexion(self):
        servidor = ServidorChat()
        with socket.socket() as oyente:
            oyente.settimeout(3)
            oyente.bind(("127.0.0.1", 0))
            oyente.listen()
            puerto = oyente.getsockname()[1]
            app = InterfazChat()
            sesiones, hilos = [], []
            def crear_sesion(ip, alias):
                sesion = SesionChat(ip, alias, puerto)
                sesiones.append(sesion)
                return sesion
            with patch("interfaz_chat.SesionChat", side_effect=crear_sesion):
                async with app.run_test(size=(100, 32)) as piloto:
                    try:
                        for vuelta in range(2):
                            app.query_one("#alias", Input).value = "Ana"
                            await piloto.click("#conectar")
                            conexion, direccion = await asyncio.to_thread(oyente.accept)
                            hilo = threading.Thread(target=servidor._atender_cliente,
                                                    args=(conexion, direccion), daemon=True)
                            hilo.start()
                            hilos.append(hilo)
                            await piloto.pause(0.2)
                            self.assertTrue(app.conectado)
                            await piloto.press("H", "o", "l", "a", "enter")
                            await piloto.pause(0.2)
                            self.assertEqual(app.query_one("#mensaje", Input).value, "")
                            lineas = "\n".join(linea.text for linea in app.query_one("#historial", RichLog).lines)
                            self.assertIn("[Ana]: Hola", lineas)
                            # La misma ruta maneja el botón y el atajo de desconexión.
                            if vuelta == 0:
                                await piloto.click("#desconectar")
                            else:
                                app.query_one("#mensaje", Input).value = "/salir"
                                await piloto.press("enter")
                            await piloto.pause(0.25)
                            self.assertIsNone(app.sesion)
                            self.assertFalse(app.query_one("#conectar").disabled)
                    finally:
                        for sesion in sesiones:
                            sesion.desconectar()
                            await asyncio.to_thread(sesion.join, 3)
                        for hilo in hilos:
                            await asyncio.to_thread(hilo.join, 3)
                            self.assertFalse(hilo.is_alive())


if __name__ == "__main__":
    unittest.main()
