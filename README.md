# Chat multiusuario LAN

Chat TCP en Python 3.10 o superior con cliente gráfico Tkinter/ttk y cliente de
consola. Solo utiliza la biblioteca estándar. Los equipos deben tener acceso
al servidor en la misma LAN por TCP **5000**.

## Instalación en Ubuntu/Linux

```bash
sudo apt update
sudo apt install python3 python3-tk git
git clone https://github.com/Itshaize/Chat-Multihilo.git
cd Chat-Multihilo
python3 -m tkinter
```

El último comando abre una ventana de comprobación de Tk. Se necesita una
sesión gráfica para ejecutar la interfaz (en Linux, acceso a X11/XWayland).
En otras distribuciones instala el paquete Tkinter de Python de su gestor de
paquetes. No se utilizan APIs exclusivas de Windows ni paquetes de pip.

## Instalación en Windows

Instala Python 3.10 o superior desde python.org, incluyendo **Tcl/Tk e IDLE**,
y Git. En PowerShell:

```powershell
git clone https://github.com/Itshaize/Chat-Multihilo.git
cd Chat-Multihilo
py -m tkinter
```

## Ejecución

1. En el equipo servidor: `python3 servidor_chat.py` en Ubuntu o
   `py servidor_chat.py` en Windows.
2. Consulta su IP LAN con `hostname -I` en Ubuntu o `ipconfig` en Windows.
3. En cada cliente: `python3 interfaz_chat.py` o `py interfaz_chat.py`.
4. Introduce un alias (máximo 20 caracteres), la IPv4 del servidor y pulsa
   **Conectar**. Para probar en un solo equipo usa `127.0.0.1`.
5. Escribe una línea y pulsa **Enviar** o Enter. Máximo 1000 caracteres.
   **Desconectar**, `/salir` o cerrar la ventana terminan la sesión.

El cliente de consola sigue disponible: `python3 cliente.py` o `py cliente.py`.
El servidor escucha en `0.0.0.0:5000`; los clientes deben indicar su IPv4 real.
Si no conecta, comprueba el cortafuegos del servidor (permitir TCP entrante
5000 en la red privada) y el aislamiento entre clientes del punto de acceso.

## Interfaz y concurrencia

El historial distingue mensajes propios en azul y recibidos en gris oscuro,
con hora local y avisos de conexión/desconexión. El estado anuncia mensajes
nuevos; el título cuenta los recibidos sin foco y se reinicia al volver a la
ventana. El sonido es opcional mediante la casilla **Sonido** y usa la campana
del sistema, cuya audibilidad depende de la configuración de cada equipo.
El historial se conserva al reconectar y solo existe en memoria.

`interfaz_chat.py` contiene `SesionChat` (red) e `InterfazChat` (presentación).
Un hilo gestiona conexión, envío y recepción mediante sockets y `select`.
Dos `queue.Queue` transportan mensajes y eventos; Tkinter se actualiza
exclusivamente en el hilo principal mediante `after()`. La espera de conexión
tiene un máximo de 5 segundos y las operaciones de socket de 1 segundo.
Desconectar durante una conexión pendiente y cerrar la ventana esperan de
forma asíncrona a que el hilo libere su socket, sin bloquear Tkinter.

## Protocolo y archivos

TCP, UTF-8, líneas delimitadas por `\n`. Primero se envía `alias\n`, después
`mensaje\n`. No se permiten saltos de línea internos. `/salir` cierra la sesión.
El servidor añade `[Alias]:` y difunde a los demás clientes; la interfaz
muestra el mensaje propio después de enviarlo, sin añadir el alias en la red.
El envío correcto al socket no constituye confirmación de lectura o entrega.

- `protocolo.py`: puerto, codificación, límites y validaciones compartidos.
- `servidor_chat.py`: registro de clientes y difusión multihilo.
- `cliente.py`: cliente de consola.
- `interfaz_chat.py`: cliente gráfico, sin dependencias externas.
- `formato.py`: mensajes y avisos del servidor.
- `prueba_chat.py`: pruebas unitarias originales.
- `prueba_interfaz.py`: integración TCP y comprobaciones de Tkinter.

## Pruebas

Ubuntu:

```bash
python3 -m unittest discover -p "prueba*.py" -v
```

Windows:

```powershell
py -m unittest discover -p "prueba*.py" -v
```

La integración usa sockets reales en `127.0.0.1` y puertos efímeros, con el
manejador del servidor existente. Comprueba alias y mensajes límite, UTF-8
fragmentado, varias líneas por escritura, difusión sin eco, mensajes inválidos,
`/salir`, intercambio con el transporte gráfico, conexión rechazada y cierre
repentino. Las pruebas de Tk verifican el procesamiento desde el hilo principal,
el historial, contador sin foco, validación y disponibilidad para reconectar.
Se omiten explícitamente si Tk o una pantalla no están disponibles.
También se comprueba que cerrar durante una conexión pendiente mantiene el
bucle gráfico activo y libera el socket. GitHub Actions ejecuta la suite en
Ubuntu (con Xvfb) y Windows, con Python 3.10 y 3.14.

## Validación manual pendiente

Las pruebas locales no sustituyen una prueba entre equipos físicos. En dos
equipos de la LAN, comprobar GUI↔GUI y GUI↔consola, avisos de entrada/salida,
mensajes con tildes, contador al cambiar a otra aplicación o minimizar,
sonido, desconexión del cable/Wi-Fi, detención del servidor, reconexión y
cierre durante la conexión. Repetir en Ubuntu y Windows y adjuntar capturas o
video de la demostración. No hay todavía evidencia de esta prueba física.

El protocolo existente no incluye cifrado, autenticación, alias únicos,
persistencia ni confirmaciones de entrega; úsalo en una LAN de confianza.
