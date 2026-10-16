"""Pruebas de conversación real con sockets TCP locales."""
import contextlib
import io
import socket
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from cliente import SocketClient
from servidor_chat import ClientHandler, ThreadedSocketServer


class PruebasChat(unittest.TestCase):
    def setUp(self):
        self.servidor = ThreadedSocketServer()
        self.conexiones = []
        self.hilos = []
        self.escucha = socket.socket()
        self.escucha.bind(('127.0.0.1', 0))
        self.escucha.listen()
        self.escucha.settimeout(3)

    def tearDown(self):
        for conexion, entrada in self.conexiones:
            try:
                conexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            if entrada:
                entrada.close()
            conexion.close()
        for hilo in self.hilos:
            hilo.join(3)
            self.assertFalse(hilo.is_alive())
        self.escucha.close()
        self.assertEqual(self.servidor.clientes, [])

    def aceptar(self):
        conexion, _ = self.escucha.accept()
        hilo = threading.Thread(target=ClientHandler(conexion, self.servidor).process)
        self.hilos.append(hilo)
        hilo.start()

    def conectar(self, nombre):
        conexion = socket.create_connection(self.escucha.getsockname(), timeout=3)
        self.aceptar()
        entrada = conexion.makefile('r', encoding='utf-8')
        self.conexiones.append((conexion, entrada))
        conexion.sendall((nombre + '\n').encode('utf-8'))
        self.assertEqual(entrada.readline(), f'Bienvenido, {nombre}.\n')
        self.assertEqual(entrada.readline(), f'--- {nombre} entró al chat ---\n')
        return conexion, entrada

    def test_tres_clientes_y_salida(self):
        ana, a = self.conectar('Ana')
        luis, b = self.conectar('Luis')
        self.assertEqual(a.readline(), '--- Luis entró al chat ---\n')
        eva, c = self.conectar('Eva')
        for entrada in [a, b]:
            self.assertEqual(entrada.readline(), '--- Eva entró al chat ---\n')
        ana.sendall('Hola compañeros\n'.encode('utf-8'))
        for entrada in [a, b, c]:
            self.assertEqual(entrada.readline(), '[Ana]: Hola compañeros\n')
        luis.sendall(b'Hola Ana\n')
        for entrada in [a, b, c]:
            self.assertEqual(entrada.readline(), '[Luis]: Hola Ana\n')
        eva.sendall(b'/salir\n')
        self.assertEqual(c.readline(), '')
        for entrada in [a, b]:
            self.assertEqual(entrada.readline(), '--- Eva salió del chat ---\n')

    def test_envios_simultaneos_y_utf8_fragmentado(self):
        ana, a = self.conectar('Ana')
        luis, b = self.conectar('Luis')
        a.readline()
        texto = '¡Hola!\nSegundo\n'.encode('utf-8')
        ana.sendall(texto[:1])
        ana.sendall(texto[1:])
        for entrada in [a, b]:
            self.assertEqual(entrada.readline(), '[Ana]: ¡Hola!\n')
            self.assertEqual(entrada.readline(), '[Ana]: Segundo\n')
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            list(ejecutor.map(lambda conexion: conexion.sendall(b'Mensaje\n'), [ana, luis]))
        for entrada in [a, b]:
            self.assertEqual({entrada.readline(), entrada.readline()},
                             {'[Ana]: Mensaje\n', '[Luis]: Mensaje\n'})

    def test_cliente_recibe_sin_enviar_y_detecta_cierre(self):
        ana, a = self.conectar('Ana')
        client = SocketClient(*self.escucha.getsockname())
        client.connect('Luis')
        self.aceptar()
        self.conexiones.append((client.conexion, None))
        a.readline()
        recibido = threading.Event()
        salida = []

        def mostrar(texto, **kwargs):
            salida.append(texto)
            if '[Ana]: Hola Luis' in texto:
                recibido.set()

        receptor = threading.Thread(target=client.receive_messages)
        try:
            with patch('builtins.print', side_effect=mostrar):
                receptor.start()
                ana.sendall(b'Hola Luis\n')
                self.assertTrue(recibido.wait(3))
                # Simular el cierre de la conexión por parte del servidor.
                with self.servidor.bloqueo:
                    self.servidor.clientes[-1].shutdown(socket.SHUT_RDWR)
                receptor.join(3)
            self.assertFalse(receptor.is_alive())
            self.assertFalse(client.activo.is_set())
            self.assertTrue(any('Pulsa Enter' in linea for linea in salida))
        finally:
            client.close()
            receptor.join(3)


if __name__ == '__main__':
    unittest.main()
