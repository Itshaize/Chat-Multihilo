"""Integración con sockets reales y comprobaciones del bucle Tk."""
import socket
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

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


class PruebasTk(unittest.TestCase):
    def setUp(self):
        try:
            self.raiz = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk no disponible: {error}")
        self.raiz.withdraw()
        self.app = InterfazChat(self.raiz)

    def tearDown(self):
        if hasattr(self, "raiz"):
            for identificador in self.raiz.tk.call("after", "info"):
                self.raiz.after_cancel(identificador)
            self.raiz.destroy()

    def test_eventos_hilo_principal_no_leidos_y_reconexion(self):
        sesion = SesionChat("127.0.0.1", "Ana")
        self.app.sesion = sesion
        principal, agregar = threading.get_ident(), self.app.agregar
        def comprobar(*args):
            self.assertEqual(threading.get_ident(), principal)
            agregar(*args)
        self.app.agregar = comprobar
        def publicar():
            sesion.eventos.put(("recibido", "[Bob]: Hola"))
            sesion.eventos.put(("enviado", "Respuesta"))
        hilo = threading.Thread(target=publicar)
        hilo.start()
        hilo.join()
        with patch.object(self.raiz, "focus_displayof", return_value=None):
            limite = time.monotonic() + 1
            while self.app.no_leidos == 0 and time.monotonic() < limite:
                self.raiz.update()
                time.sleep(0.01)
        self.assertEqual(self.app.no_leidos, 1)
        self.assertIn("(1)", self.raiz.title())
        self.assertIn("[Ana]: Respuesta", self.app.historial.get("1.0", "end"))
        self.app.al_enfocar()
        self.assertEqual(self.app.no_leidos, 0)
        sesion.eventos.put(("desconectado", "Conexión cerrada"))
        self.app.procesar_eventos()
        self.assertIsNone(self.app.sesion)
        self.assertEqual(str(self.app.conectar_boton["state"]), "normal")

    def test_validacion_y_cierre(self):
        self.app.conectar()
        self.assertIsNone(self.app.sesion)
        self.app.alias.set("Ana")
        self.app.ip.set("IP incorrecta")
        self.app.conectar()
        self.assertIsNone(self.app.sesion)
        self.app.cerrar()
        self.assertTrue(self.app.cerrando)

    def test_cerrar_durante_conexion_no_bloquea_tk(self):
        inicio, liberar = threading.Event(), threading.Event()
        conexion = MagicMock()
        conexion.__enter__.return_value = conexion
        def conectar_lento(*args):
            inicio.set()
            liberar.wait(3)
        conexion.connect.side_effect = conectar_lento
        with patch("interfaz_chat.socket.socket", return_value=conexion):
            self.app.alias.set("Ana")
            self.app.conectar()
            sesion = self.app.sesion
            try:
                self.assertTrue(inicio.wait(1))
                self.app.cerrar()
                atendido = []
                self.raiz.after(0, lambda: atendido.append(True))
                self.raiz.update()
                self.assertEqual(atendido, [True])
                self.assertTrue(sesion.is_alive())
            finally:
                liberar.set()
                sesion.join(3)
            self.assertFalse(sesion.is_alive())
            with patch.object(self.raiz, "destroy") as destruir:
                self.app.procesar_eventos()
                destruir.assert_called_once()
            conexion.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
