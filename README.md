\# Meshtastic Ping Bot



Bot para responder el comando `/ping` leyendo los mensajes recibidos por canales mediante la API de Meshtastic para Python 3.



El objetivo es disponer de una herramienta simple para verificar conectividad, obtener información básica del enlace de radio y responder automáticamente a solicitudes realizadas desde la red Meshtastic.



\---



\## Características



\- Respuesta automática al comando `/ping`

\- Soporte para múltiples canales configurables

\- Autodetección del dispositivo Meshtastic conectado por USB

\- Posibilidad de definir manualmente el puerto serie

\- Protección contra paquetes duplicados

\- Sistema de cooldown para evitar spam

\- Obtención automática del nombre del nodo remoto

\- Compatibilidad con diferentes estructuras de la API de Meshtastic

\- Registro de eventos en consola y archivo de log

\- Información de calidad del enlace:

&#x20; - RSSI

&#x20; - SNR

&#x20; - Saltos (Hops)

\- Hora UTC (GMT) en las respuestas

\- Configuración sencilla mediante variables dentro del script

\- Diseñado para funcionar de forma continua



\---



\## Requisitos



\### Hardware



Cualquier dispositivo compatible con Meshtastic y soportado por la librería oficial de Python.



\### Software



\- Debian 13

\- Python 3

\- Meshtastic Python API 2.7.11 o superior



\---



\## Instalación



\### Instalar dependencias del sistema



```bash

sudo apt install -y \\

&#x20;   python3 \\

&#x20;   python3-pip \\

&#x20;   python3-venv \\

&#x20;   python3-dev \\

&#x20;   build-essential \\

&#x20;   usbutils

```



\### Crear entorno virtual



```bash

mkdir -p \~/meshtastic-bot

cd \~/meshtastic-bot



python3 -m venv .venv

source .venv/bin/activate



python -m pip install --upgrade pip

```



\### Instalar Meshtastic



```bash

pip install --upgrade meshtastic

```



\### Descargar el script



```bash

git clone https://github.com/bysepa1/Meshtastic\_Bot\_ping.git



cd Meshtastic\_Bot\_ping

```



\## Configuración



Toda la configuración se realiza modificando las variables ubicadas al inicio del script.



\### Puerto serie



Autodetección:



```python

SERIAL\_PORT = None

```



Puerto manual:



```python

SERIAL\_PORT = "/dev/ttyACM0"

```



\### Canales monitorizados



```python

CHANNEL\_NAMES = (

&#x20;   "Bots",

&#x20;   "Test",

)

```



\### Comando



```python

COMMAND = "/ping"

```



\### Información del bot



```python

LOCATION = "UBICACIÓN"

BOT\_AUTHOR = "@BySepa"

```



\## Uso



```bash

python3 ping\_bot.py

```



\## Ejemplo



Usuario:



```text

/ping

```



Respuesta:



```text

/pong

Origen: Nodo\_Remoto

Nodo: Nodo\_Bot | @BySepa

Saltos: 2

Hora GMT: 18:42:15 GMT

SNR: 10.5 dB

RSSI: -97 dBm

Ubicación: Valencia, España

```



\## Logging



El bot registra su actividad en:



```text

meshtastic\_bot.log

```



\## Compatibilidad



\- Debian 13

\- Meshtastic Python API 2.7.11 o superior



\## Licencia



GNU General Public License v3.0 (GPLv3)



https://www.gnu.org/licenses/gpl-3.0.html



\## Autor



BySepa



\- https://bysepa.net

\- https://www.linktr.ee/BySepa

