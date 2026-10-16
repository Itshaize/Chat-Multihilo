# Chat LAN multihilo básico

Chat real entre compañeros, sin dependencias externas. Usa Python 3 y TCP 8080.
Se mantienen las clases SocketClient, ClientHandler y ThreadedSocketServer
del ejemplo, adaptadas para repartir mensajes.

## Actualizar todos los equipos

Dentro de la carpeta Chat-Multihilo:

```bash
git pull origin main
```

Hay que actualizar tanto el servidor como todos los clientes: el cliente
anterior de eco utiliza otro protocolo y no es compatible.

## Equipo servidor

```bash
python3 servidor_chat.py
```

Escucha en 0.0.0.0:8080. Deja esa terminal abierta.
Consulta la IP con hostname -I (Ubuntu) o ipconfig (Windows) y compártela.

## Cada compañero

```bash
python3 cliente.py
```

Introduce tu nombre y la IP del equipo servidor.
127.0.0.1 solo sirve si el servidor está en tu propia computadora.
interfaz_chat.py también abre el mismo cliente.

```text
------------------------------
    BIENVENIDO AL CHAT
------------------------------
Tu nombre: Ana
IP del servidor [127.0.0.1]: 192.168.1.20
------------------------------
Escribe un mensaje y pulsa Enter.
Escribe /salir para terminar.
------------------------------
Bienvenido, Ana.
--- Luis entró al chat ---
[Luis]: Hola a todos
> Hola Luis
[Ana]: Hola Luis
```

Todos los conectados reciben los mensajes, incluido quien los envía.
Escribe /salir para salir. Detén el servidor con Ctrl+C.
Si el servidor se desconecta, pulsa Enter para cerrar el cliente.

## Cómo funciona

El cliente mantiene una conexión abierta durante toda la conversación.
Primero envía su nombre; después, cada mensaje termina en un salto de línea.
Un hilo del cliente recibe mientras el hilo principal lee el teclado.
El servidor crea un hilo por cliente y reparte los mensajes a todos.
Un Lock evita que los envíos concurrentes se mezclen.

Los mensajes entrantes pueden aparecer junto al indicador > mientras escribes.
La entrada sigue funcionando; es una consola básica.
No hay historial persistente, cuentas ni cifrado.

## Red

Los equipos deben poder comunicarse en la misma red y el servidor debe aceptar
TCP entrante al puerto 8080. En VirtualBox, un adaptador puente puede permitir
que la máquina virtual esté en la misma red que los compañeros.

Connection refused: revisa que el servidor esté iniciado y la IP sea correcta.
Si se agota el tiempo de conexión, revisa la red y el cortafuegos.

## Pruebas

```bash
python3 -m unittest discover -p "prueba*.py" -v
```

Pruebas con TCP local real; la prueba entre equipos se hace en la red de clase.
