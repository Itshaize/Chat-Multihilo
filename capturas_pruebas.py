"""Ejecuta la suite y exporta capturas SVG reproducibles de una sesión TCP real."""
import argparse
import asyncio
import io
import logging
import platform
import socket
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.text import Text
from textual import events
from textual.widgets import Input, RichLog

from interfaz_chat import InterfazChat
from protocolo import CODIFICACION
from red_chat import SesionChat
from servidor_chat import ServidorChat


async def capturar(salida):
    servidor = ServidorChat()
    app = InterfazChat()
    # La evidencia usa colores aunque el entorno de CI defina NO_COLOR.
    app.no_color = False
    sesiones, hilos = [], []
    with socket.socket() as oyente:
        oyente.bind(("127.0.0.1", 0))
        oyente.listen()
        oyente.settimeout(3)
        puerto = oyente.getsockname()[1]

        def crear_sesion(ip, alias):
            sesion = SesionChat(ip, alias, puerto)
            sesiones.append(sesion)
            return sesion

        async def aceptar():
            conexion, direccion = await asyncio.to_thread(oyente.accept)
            hilo = threading.Thread(target=servidor._atender_cliente,
                                    args=(conexion, direccion), daemon=True)
            hilo.start()
            hilos.append(hilo)

        with patch("interfaz_chat.SesionChat", side_effect=crear_sesion):
            async with app.run_test(size=(100, 32)) as piloto:
                app.save_screenshot("01-tui-inicial.svg", str(salida))
                try:
                    app.query_one("#alias", Input).value = "Ana"
                    await piloto.click("#conectar")
                    await aceptar()
                    await piloto.pause(0.2)
                    assert app.conectado, "La TUI no se conectó"
                    with socket.create_connection(("127.0.0.1", puerto), timeout=3) as otro:
                        await aceptar()
                        with otro.makefile("r", encoding=CODIFICACION) as entrada:
                            otro.sendall(b"Luis\n")
                            bienvenida = await asyncio.to_thread(entrada.readline)
                            assert "Bienvenido, Luis" in bienvenida
                            await piloto.pause(0.15)
                            app.query_one("#mensaje", Input).value = "Hola, Luis. TUI en Python lista."
                            await piloto.click("#enviar")
                            recibido = await asyncio.to_thread(entrada.readline)
                            assert recibido == "[Ana]: Hola, Luis. TUI en Python lista.\n"
                            otro.sendall("Recibido. ¡Conexión TCP correcta!\n".encode(CODIFICACION))
                            await piloto.pause(0.2)
                            historial = "\n".join(linea.text for linea in app.query_one("#historial", RichLog).lines)
                            assert "[Luis]: Recibido." in historial
                            app.save_screenshot("02-tui-conversacion.svg", str(salida))
                            # Se simula solo la pérdida de foco; el mensaje viaja por TCP real.
                            app.on_app_blur(events.AppBlur())
                            otro.sendall("Mensaje mientras la terminal no tiene foco.\n".encode(CODIFICACION))
                            await piloto.pause(0.2)
                            assert app.no_leidos == 1
                            app.save_screenshot("03-tui-no-leidos.svg", str(salida))
                            app.on_app_focus(events.AppFocus())
                            assert app.no_leidos == 0
                            otro.sendall(b"/salir\n")
                    await piloto.pause(0.15)
                    await piloto.click("#desconectar")
                    await piloto.pause(0.25)
                    assert app.sesion is None
                    app.save_screenshot("04-tui-desconectada.svg", str(salida))
                finally:
                    for sesion in sesiones:
                        sesion.desconectar()
                        await asyncio.to_thread(sesion.join, 3)
                    for hilo in hilos:
                        await asyncio.to_thread(hilo.join, 3)
                        assert not hilo.is_alive()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path("evidencias"))
    salida = parser.parse_args().salida.resolve()
    salida.mkdir(parents=True, exist_ok=True)
    # El resumen visual conserva la salida real de unittest, sin logs de mensajes.
    logging.disable(logging.CRITICAL)
    registro = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="prueba*.py")
    resultado = unittest.TextTestRunner(stream=registro, verbosity=2).run(suite)
    texto = (f"{platform.system()} · Python {platform.python_version()}\n"
             "python -m unittest discover -p 'prueba*.py' -v\n\n" + registro.getvalue())
    (salida / "pruebas.txt").write_text(texto, encoding="utf-8")
    consola = Console(record=True, width=110, file=io.StringIO())
    consola.print(Text(texto))
    consola.save_svg(str(salida / "05-resultado-pruebas.svg"), title="Salida real de unittest")
    print(texto)
    if not resultado.wasSuccessful():
        raise SystemExit(1)
    asyncio.run(capturar(salida))
    print(f"Capturas SVG guardadas en {salida}")


if __name__ == "__main__":
    main()
