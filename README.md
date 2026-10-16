# Chat multiusuario LAN · TUI en Python

Cliente de terminal con **Textual**, estilo TUI de paneles similar a Ratatui.
Se ejecuta en Linux y Windows sin escritorio gráfico, Tkinter ni Rust.
El servidor y el cliente de consola originales siguen escritos en Python y
solo necesitan la biblioteca estándar. La TUI añade Textual como dependencia.

## Instalación en Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
git clone --branch feature/interfaz-chat https://github.com/Itshaize/Chat-Multihilo.git
cd Chat-Multihilo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

En otras distribuciones instala Python 3.10 o superior y soporte para venv.
Utiliza una terminal UTF-8, preferiblemente de 80 columnas y 24 filas o más.
También hay un diseño compacto para terminales de menos de 75 columnas.

## Instalación en Windows

Instala Python 3.10 o superior y Git. En PowerShell:

```powershell
git clone --branch feature/interfaz-chat https://github.com/Itshaize/Chat-Multihilo.git
cd Chat-Multihilo
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Usa Windows Terminal o una terminal con soporte UTF-8/ANSI.
En Windows los comandos siguientes pueden ejecutarse sustituyendo `python`
por `.\.venv\Scripts\python` si el entorno no está activado.

## Prueba local y uso en LAN

Desde la carpeta del repositorio, en una terminal inicia el servidor:

```bash
python servidor_chat.py
```

En otras dos terminales, activa el entorno y ejecuta un cliente en cada una:

```bash
python interfaz_chat.py
```

Introduce alias distintos e IP `127.0.0.1`. En una LAN, usa la IPv4 real del
servidor: consúltala con `hostname -I` en Linux o `ipconfig` en Windows.
El servidor escucha en `0.0.0.0:5000`; permite TCP entrante al puerto 5000 en
su cortafuegos privado y comprueba el aislamiento de clientes del Wi-Fi.

El cliente de consola permanece disponible con `python cliente.py`.
Para detener el servidor utiliza Ctrl+C.

## Controles de la TUI

- **Tab / Shift+Tab**: recorre campos, botones, historial y sonido.
- **Enter** en alias: pasa a la IP; en IP: conecta; en mensaje: envía.
- **Conectar / Enviar / Desconectar**: botones utilizables con teclado o ratón.
- **Ctrl+D**: desconecta; `/salir` en el mensaje también termina la sesión.
- **Ctrl+Q o Ctrl+C**: cierra limpiamente el cliente y restaura la terminal.
- **F2** o casilla **Sonido**: activa/desactiva la campana de la terminal.
- **Ctrl+L**: marca los mensajes como leídos manualmente.
- Historial desplazable con ratón o teclado al enfocarlo.

Mensajes propios en cian, recibidos en gris claro y avisos en gris discreto,
con hora local. El historial anuncia mensajes nuevos y la cabecera cuenta
los recibidos sin foco, reiniciando el contador al volver a la terminal.
**El aviso de foco depende de que el emulador de terminal lo comunique**;
si no lo soporta, no puede detectarse automáticamente. La campana también
depende de la configuración del emulador y puede ser visual o inaudible.
El historial vive en memoria y conserva hasta 5000 líneas renderizadas.

## Protocolo y concurrencia

Se reutilizan directamente las constantes y validaciones de `protocolo.py`:
TCP **5000**, UTF-8, alias máximo 20, mensaje máximo 1000 y `/salir`.
Primero se envía `alias\n`, después `mensaje\n`, sin saltos de línea internos.
El servidor añade `[Alias]:` y difunde a los demás clientes. La TUI muestra
el mensaje propio tras enviarlo al socket; esto no confirma entrega o lectura.

`red_chat.py` mantiene conexión, envío y recepción en un hilo `threading`.
Dos `queue.Queue` transportan salida y eventos. Solo el bucle principal de
Textual actualiza widgets, consultando eventos mediante `set_interval()`.
La conexión espera hasta 5 segundos y las operaciones de socket hasta 1.
Cerrar durante una conexión pendiente conserva la respuesta de la interfaz
hasta que el hilo libera el socket. No se modifican servidor ni consola.

## Pruebas y capturas reproducibles

Con el entorno activado:

```bash
python -m unittest discover -p "prueba*.py" -v
python capturas_pruebas.py --salida evidencias
```

La suite incluye las pruebas originales, integración TCP real en loopback
con puertos efímeros y pruebas de TUI mediante `App.run_test()` y Pilot.
Verifica UTF-8 fragmentado, límites, alias inválido, difusión sin eco,
`/salir`, conexión rechazada, cierre remoto, hilo principal, texto literal,
contador sin foco, botones, teclado, terminal compacta y reconexión real.
No necesita Xvfb, Tkinter ni pantalla gráfica. GitHub Actions ejecuta la
suite en Ubuntu y Windows con Python 3.10 y 3.14.

`capturas_pruebas.py` ejecuta la suite y exporta su salida real a `pruebas.txt`
y SVG. Después abre una sesión de prueba con el servidor Python real y
exporta capturas SVG de la TUI inicial, conversación, mensajes no leídos y
desconexión. Son capturas del renderizador de Textual durante pruebas
sin terminal visible. Solo la pérdida de foco se simula; los mensajes sí
viajan por TCP. No representan pruebas entre equipos físicos ni una captura
del escritorio Linux. Las evidencias pueden abrirse en cualquier navegador.

## Archivos

- `interfaz_chat.py`: TUI Textual, presentación y controles.
- `red_chat.py`: transporte TCP en segundo plano.
- `requirements.txt`: versión de Textual probada.
- `servidor_chat.py`, `cliente.py`: servidor y consola existentes.
- `protocolo.py`, `formato.py`: contrato y formato compartidos.
- `prueba_chat.py`, `prueba_interfaz.py`: suite de pruebas.
- `capturas_pruebas.py`: generación reproducible de evidencias.

## Validación pendiente

Falta comprobar la experiencia en emuladores de terminal reales de Linux y
Windows: foco, sonido, redimensionado y restauración de la terminal al salir.
También falta probar entre equipos físicos de una LAN: TUI↔TUI y TUI↔consola,
con desconexión de cable/Wi-Fi, reconexión y detención del servidor.
Las pruebas en loopback no sustituyen esta demostración.

El protocolo existente no ofrece cifrado, autenticación, alias únicos,
persistencia ni confirmaciones de entrega; úsalo en una LAN de confianza.
