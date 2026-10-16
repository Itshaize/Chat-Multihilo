"""Cliente TCP concurrente para un chat multiusuario por consola.

Protocolo compatible con servidor_chat.py:
- UTF-8.
- Cada mensaje termina en '\n'.
- La primera línea enviada al conectarse contiene el alias del usuario.
- Las siguientes líneas contienen los mensajes de chat.
- El servidor devuelve mensajes ya identificados, por ejemplo: [Ana]: Hola.
"""

import socket
import threading

PUERTO_PREDETERMINADO = 8080


def solicitar_alias():
    """Solicita un nombre de usuario válido para el servidor."""
    while True:
        alias = input("Nombre de usuario: ").strip()
        if 1 <= len(alias) <= 24:
            return alias
        print("El alias debe tener entre 1 y 24 caracteres.")


def recibir_mensajes(conexion, detener):
    """Escucha mensajes del servidor en un hilo independiente."""
    try:
        # makefile lee líneas completas, incluso si TCP divide un mensaje.
        with conexion.makefile("r", encoding="utf-8", errors="replace") as entrada:
            for linea in entrada:
                if detener.is_set():
                    break
                mensaje = linea.rstrip("\r\n")
                if mensaje:
                    print(f"\n{mensaje}\n> ", end="", flush=True)
            if not detener.is_set():
                print("\nEl servidor cerró la conexión.")
    except (OSError, ValueError) as error:
        if not detener.is_set():
            print(f"\nError al recibir mensajes: {error}")
    finally:
        detener.set()


def enviar_mensajes(conexion, detener):
    """Lee el teclado y envía mensajes sin bloquear la recepción."""
    try:
        while not detener.is_set():
            mensaje = input("> ").strip()
            if mensaje.lower() == "/salir":
                break
            if mensaje:
                conexion.sendall((mensaje + "\n").encode("utf-8"))
    except (OSError, EOFError) as error:
        if not detener.is_set():
            print(f"\nNo se pudo enviar el mensaje: {error}")
    finally:
        detener.set()


def iniciar_cliente():
    """Conecta el cliente y ejecuta envío/recepción en hilos separados."""
    ip_servidor = input("IP del servidor [127.0.0.1]: ").strip() or "127.0.0.1"
    alias = solicitar_alias()
    detener = threading.Event()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conexion:
            conexion.connect((ip_servidor, PUERTO_PREDETERMINADO))
            conexion.sendall((alias + "\n").encode("utf-8"))
            print(f"Conectado como {alias}. Escribe /salir para terminar.")

            hilo_recepcion = threading.Thread(
                target=recibir_mensajes,
                args=(conexion, detener),
                daemon=True,
                name="recepcion",
            )
            hilo_envio = threading.Thread(
                target=enviar_mensajes,
                args=(conexion, detener),
                daemon=True,
                name="envio",
            )
            hilo_recepcion.start()
            hilo_envio.start()

            # Mantiene el programa en ejecución y permite Ctrl+C.
            while not detener.wait(0.1):
                pass

            try:
                conexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    except ConnectionRefusedError:
        print("No hay un servidor escuchando en esa IP y puerto.")
    except (TimeoutError, OSError) as error:
        print(f"No fue posible conectarse: {error}")
    except KeyboardInterrupt:
        print("\nCerrando cliente...")
    finally:
        detener.set()


if __name__ == "__main__":
    iniciar_cliente()
