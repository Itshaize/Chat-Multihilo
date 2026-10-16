# Chat Multiusuario LAN (consola)

Práctica de Sistemas Distribuidos en Python 3. El servidor TCP gestiona múltiples participantes y difunde los mensajes a los demás clientes conectados.

## Requisitos
- Python 3.10 o superior. Solo biblioteca estándar.
- Equipos conectados a la misma LAN con acceso TCP al puerto **5000**.

## Ejecución
1. Descargar/clonar el repositorio.
2. Iniciar el servidor en un equipo: \`python3 servidor_chat.py\` (Windows: \`py servidor_chat.py\`).
3. Averiguar la IP LAN del servidor: \`hostname -I\` en Linux o \`ipconfig\` en Windows.
4. En cada equipo cliente ejecutar \`python3 cliente.py\` (Windows: \`py cliente.py\`), introducir alias e IP LAN del servidor.
5. Escribir mensajes; usar \`/salir\` para cerrar. Para pruebas en un solo equipo, aceptar la IP predeterminada \`127.0.0.1\`.

**Importante:** el servidor escucha en \`0.0.0.0:5000\`, pero los clientes deben usar su IP LAN real. Verificar cortafuegos y aislamiento de clientes si la red impide conexiones.

## Archivos
- \`servidor_chat.py\`: acepta conexiones, mantiene registro seguro y hace broadcast.
- \`cliente.py\`: recibe y envía en paralelo con \`threading\`.
- \`protocolo.py\`: constantes, validaciones y contrato de texto UTF-8.
- \`formato.py\`: formato de mensajes y avisos.
- \`prueba_chat.py\`: pruebas unitarias del protocolo y formateo.

## Protocolo
TCP, UTF-8 y líneas delimitadas por \`\n\`. La primera línea enviada por cada cliente contiene su alias (1–20 caracteres). Las siguientes contienen mensajes (1–1000 caracteres). El servidor agrega el prefijo \`[Alias]:\` y difunde a los demás clientes. El comando \`/salir\` cierra la sesión.

## Diseño y concurrencia
Separación de responsabilidades (SRP): configuración y validación en \`protocolo.py\`, presentación en \`formato.py\`, conexiones y difusión en servidor. El formateador se inyecta al servidor, facilitando extenderlo o reemplazarlo (DIP/OCP). Un hilo por conexión; el registro usa \`Lock\` y cada socket tiene un bloqueo de envío para evitar mezcla de datos. El cliente usa un hilo para entrada y otro flujo para recepción.

## Pruebas
Ejecutar \`python3 prueba_chat.py\`. Prueba manual: iniciar servidor y dos clientes en terminales diferentes, verificar mensajes en ambos sentidos y desconectar un cliente; el servidor debe continuar funcionando.

**Evidencia pendiente:** añadir captura o video real de la demostración entre dos terminales ubicadas en dispositivos distintos de una LAN. Las pruebas locales no sustituyen esta validación.
