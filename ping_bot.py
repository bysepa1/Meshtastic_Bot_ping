#!/usr/bin/env python3

# ============================================================
# DESCRIPCIÓN
# ============================================================
# 
# Bot para responder el comando "/ping" leyendo los mensajes
# por medio de la API de meshtastic de Python3
#
# Requisitos de paquetes (Debian 13):
#   sudo apt install -y python3 \
#    python3-pip \
#    python3-venv \
#    python3-dev \
#    build-essential \
#    usbutils
#
# Crear entorno virtual
#
#    mkdir -p ~/meshtastic-bot
#    cd ~/meshtastic-bot
#    python3 -m venv .venv
#    source .venv/bin/activate
#    python -m pip install --upgrade pip
#
# Instalar Meshtastic
#
#    pip install --upgrade meshtastic
#
# Ejecutar
#    python3 ping_bot.py

import logging
import sys
import time
from collections import OrderedDict
from datetime import datetime, timezone

import meshtastic.serial_interface
from pubsub import pub


# ============================================================
# CONFIGURACIÓN
# ============================================================

# ------------------------------------------------------------
# PUERTO SERIE
# ------------------------------------------------------------
#
# None = autodetección del dispositivo Meshtastic.
#
# Si quieres especificarlo manualmente:
#
# SERIAL_PORT = "/dev/ttyACM0"
# SERIAL_PORT = "/dev/ttyUSB0"

SERIAL_PORT = None


# ------------------------------------------------------------
# CANALES A MONITORIZAR
# ------------------------------------------------------------
#
# El bot escuchará /ping en estos canales.
#
# Los nombres deben coincidir EXACTAMENTE con los nombres
# configurados en Meshtastic.

CHANNEL_NAMES = (
    "Bots",
    "Test",
)


# ------------------------------------------------------------
# COMANDO
# ------------------------------------------------------------

COMMAND = "/ping"


# ------------------------------------------------------------
# INFORMACIÓN DEL BOT
# ------------------------------------------------------------

LOCATION = "UBICACIÓN"

BOT_AUTHOR = "@BySepa"


# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------

LOG_FILE = "meshtastic_bot.log"

# Niveles disponibles:
#
# logging.DEBUG
# logging.INFO
# logging.WARNING
# logging.ERROR

LOG_LEVEL = logging.INFO


# ------------------------------------------------------------
# DEDUPLICACIÓN
# ------------------------------------------------------------
#
# Tiempo durante el cual se recuerdan los paquetes procesados.
#
# Si el mismo paquete vuelve a aparecer dentro de este período,
# no se responderá nuevamente.

DEDUP_TTL_SECONDS = 120


# ------------------------------------------------------------
# COOLDOWN
# ------------------------------------------------------------
#
# Tiempo mínimo entre comandos /ping del mismo nodo
# en el mismo canal.
#
# 0 = desactivado.
#
# Ejemplo:
#
# COMMAND_COOLDOWN_SECONDS = 5
#
# significa que el mismo nodo solo podrá obtener una respuesta
# cada 5 segundos por canal.

COMMAND_COOLDOWN_SECONDS = 5


# ============================================================
# VARIABLES GLOBALES
# ============================================================

interface = None


# Diccionario con los índices de los canales.
#
# Ejemplo:
#
# {
#     "Bots": 0,
#     "Test": 1,
# }

channel_indexes = {}


# Paquetes procesados recientemente.

processed_packets = OrderedDict()


# Último comando procesado por nodo/canal.

last_command_time = {}


# ============================================================
# LOGGING
# ============================================================

def setup_logging():
    """
    Configura logging en consola y archivo.
    """

    root_logger = logging.getLogger()

    root_logger.setLevel(
        LOG_LEVEL
    )


    # Evitar crear handlers duplicados.

    if root_logger.handlers:
        return


    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )


    # --------------------------------------------------------
    # Consola
    # --------------------------------------------------------

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter
    )


    # --------------------------------------------------------
    # Archivo
    # --------------------------------------------------------

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )

    file_handler.setFormatter(
        formatter
    )


    root_logger.addHandler(
        console_handler
    )

    root_logger.addHandler(
        file_handler
    )


logger = logging.getLogger(
    __name__
)


# ============================================================
# DEDUPLICACIÓN
# ============================================================

def cleanup_processed_packets():
    """
    Elimina de memoria los paquetes cuyo TTL ha expirado.
    """

    now = time.monotonic()


    while processed_packets:

        _, timestamp = next(
            iter(
                processed_packets.items()
            )
        )


        if (
            now - timestamp
            < DEDUP_TTL_SECONDS
        ):
            break


        processed_packets.popitem(
            last=False
        )


def is_duplicate_packet(packet):
    """
    Comprueba si un paquete ya fue procesado.

    Utiliza el ID del paquete cuando está disponible.

    Si no existe ID, utiliza una clave alternativa basada
    en origen, canal y texto.
    """

    cleanup_processed_packets()


    packet_id = packet.get(
        "id"
    )


    source_node = packet.get(
        "from"
    )


    channel = packet.get(
        "channel",
        0,
    )


    decoded = packet.get(
        "decoded",
        {},
    )


    text = decoded.get(
        "text",
        "",
    )


    # --------------------------------------------------------
    # ID de paquete
    # --------------------------------------------------------

    if packet_id is not None:

        packet_key = (
            "id",
            packet_id,
        )


    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    else:

        packet_key = (
            "fallback",
            source_node,
            channel,
            text,
        )


    # --------------------------------------------------------
    # Comprobar duplicado
    # --------------------------------------------------------

    if packet_key in processed_packets:

        return True


    # --------------------------------------------------------
    # Registrar paquete
    # --------------------------------------------------------

    processed_packets[
        packet_key
    ] = time.monotonic()


    return False


# ============================================================
# CANALES
# ============================================================

def get_channel_name(channel):
    """
    Obtiene el nombre de un canal.

    Soporta estructuras basadas en objetos y diccionarios.
    """

    # --------------------------------------------------------
    # Estructura como objeto
    # --------------------------------------------------------

    try:

        name = channel.settings.name


        if name is not None:

            return name


    except AttributeError:

        pass


    # --------------------------------------------------------
    # Estructura como diccionario
    # --------------------------------------------------------

    try:

        name = channel.get(
            "settings",
            {},
        ).get(
            "name",
            "",
        )


        if name is not None:

            return name


    except (
        AttributeError,
        TypeError,
    ):

        pass


    return ""


def get_channels(iface):
    """
    Obtiene los canales del nodo local.

    La API actual utiliza un diccionario.

    También soporta listas para compatibilidad.
    """

    try:

        channels = (
            iface.localNode.channels
        )


    except Exception:

        logger.exception(
            "No se pudieron obtener "
            "los canales."
        )


        return []


    # --------------------------------------------------------
    # Diccionario
    # --------------------------------------------------------

    if isinstance(
        channels,
        dict,
    ):

        return channels.items()


    # --------------------------------------------------------
    # Lista
    # --------------------------------------------------------

    if isinstance(
        channels,
        list,
    ):

        return enumerate(
            channels
        )


    logger.error(
        "Formato de canales desconocido: %s",
        type(channels),
    )


    return []


def find_channels(
    iface,
    channel_names,
):
    """
    Busca todos los canales configurados.

    Devuelve:

        {
            "Bots": 0,
            "Test": 1,
        }
    """

    found = {}


    logger.info(
        "Canales encontrados:"
    )


    for index, channel in get_channels(
        iface
    ):

        name = get_channel_name(
            channel
        )


        logger.info(
            "  Canal %s: %s",
            index,
            name or "<sin nombre>",
        )


        if name in channel_names:

            found[name] = index


    return found


# ============================================================
# NOMBRE DEL NODO LOCAL
# ============================================================

def get_node_name(iface):
    """
    Obtiene el nombre largo del nodo local.
    """

    try:

        name = iface.getLongName()


        if name:

            return name


    except Exception as exc:

        logger.warning(
            "No se pudo obtener el nombre "
            "del nodo local: %s",
            exc,
        )


    return "Nodo desconocido"


# ============================================================
# INFORMACIÓN DEL NODO DE ORIGEN
# ============================================================

def get_source_node_id(packet):
    """
    Obtiene el número del nodo que originó el paquete.
    """

    return packet.get(
        "from"
    )


def extract_long_name(node):
    """
    Intenta obtener longName de diferentes estructuras
    posibles de NodeInfo.
    """

    if node is None:

        return None


    # --------------------------------------------------------
    # Estructura como objeto
    # --------------------------------------------------------

    try:

        user = node.user


        if user:

            name = user.longName


            if name:

                return name


    except AttributeError:

        pass


    # --------------------------------------------------------
    # Estructura como diccionario
    # --------------------------------------------------------

    try:

        user = node.get(
            "user",
            {},
        )


        if isinstance(
            user,
            dict,
        ):

            name = user.get(
                "longName"
            )


            if name:

                return name


    except AttributeError:

        pass


    return None


def get_source_node_name(
    packet,
    iface,
):
    """
    Obtiene el nombre largo del nodo de origen.

    Se intenta:

    1. nodesByNum
    2. nodes utilizando fromId
    3. node ID directamente
    4. número del nodo como último recurso
    """

    node_num = get_source_node_id(
        packet
    )


    if node_num is None:

        return "Nodo desconocido"


    # ========================================================
    # MÉTODO 1: nodesByNum
    # ========================================================

    try:

        nodes_by_num = getattr(
            iface,
            "nodesByNum",
            None,
        )


        if nodes_by_num:

            node = nodes_by_num.get(
                node_num
            )


            name = extract_long_name(
                node
            )


            if name:

                return name


    except Exception as exc:

        logger.debug(
            "Error consultando nodesByNum: %s",
            exc,
        )


    # ========================================================
    # MÉTODO 2: nodes + fromId
    # ========================================================

    try:

        nodes = getattr(
            iface,
            "nodes",
            None,
        )


        node_id = packet.get(
            "fromId"
        )


        if nodes and node_id:

            node = nodes.get(
                node_id
            )


            name = extract_long_name(
                node
            )


            if name:

                return name


    except Exception as exc:

        logger.debug(
            "Error consultando nodes: %s",
            exc,
        )


    # ========================================================
    # MÉTODO 3: convertir nodeNum a nodeId
    # ========================================================
    #
    # Normalmente:
    #
    # !XXXXXXXX
    #
    # donde XXXXXXXX es el nodeNum en hexadecimal.

    try:

        node_id = (
            f"!{node_num:08x}"
        )


        nodes = getattr(
            iface,
            "nodes",
            None,
        )


        if nodes:

            node = nodes.get(
                node_id
            )


            name = extract_long_name(
                node
            )


            if name:

                return name


    except Exception as exc:

        logger.debug(
            "Error buscando nodeId: %s",
            exc,
        )


    # ========================================================
    # ÚLTIMO RECURSO
    # ========================================================

    try:

        return (
            f"!{node_num:08x}"
        )


    except Exception:

        return (
            f"Nodo {node_num}"
        )


# ============================================================
# INFORMACIÓN DEL PAQUETE
# ============================================================

def get_hops(packet):
    """
    Calcula los saltos consumidos:

        hopStart - hopLimit
    """

    try:

        hop_start = packet.get(
            "hopStart"
        )


        hop_limit = packet.get(
            "hopLimit"
        )


        if hop_start is None:

            return 0


        if hop_limit is None:

            return 0


        hops = (
            hop_start
            - hop_limit
        )


        return max(
            0,
            hops,
        )


    except Exception as exc:

        logger.warning(
            "No se pudieron calcular "
            "los saltos: %s",
            exc,
        )


        return 0


def get_rssi(packet):
    """
    Obtiene RSSI.
    """

    rssi = packet.get(
        "rxRssi"
    )


    if rssi is not None:

        return rssi


    return packet.get(
        "rssi"
    )


def get_snr(packet):
    """
    Obtiene SNR.
    """

    snr = packet.get(
        "rxSnr"
    )


    if snr is not None:

        return snr


    return packet.get(
        "snr"
    )


# ============================================================
# HORA UTC
# ============================================================

def get_gmt_time():
    """
    Devuelve la hora actual en UTC.

    Formato:

        HH:MM:SS GMT
    """

    now = datetime.now(
        timezone.utc
    )


    return now.strftime(
        "%H:%M:%S GMT"
    )


# ============================================================
# COOLDOWN
# ============================================================

def is_on_cooldown(
    source_node_id,
    channel_index,
):
    """
    Comprueba si el nodo está en cooldown.
    """

    if (
        COMMAND_COOLDOWN_SECONDS
        <= 0
    ):

        return False


    key = (
        source_node_id,
        channel_index,
    )


    previous = last_command_time.get(
        key
    )


    if previous is None:

        return False


    elapsed = (
        time.monotonic()
        - previous
    )


    if (
        elapsed
        < COMMAND_COOLDOWN_SECONDS
    ):

        remaining = (
            COMMAND_COOLDOWN_SECONDS
            - elapsed
        )


        logger.info(
            "Comando ignorado por cooldown | "
            "nodo=%s | "
            "canal=%s | "
            "restante=%.1fs",
            source_node_id,
            channel_index,
            remaining,
        )


        return True


    return False


def register_command(
    source_node_id,
    channel_index,
):
    """
    Registra el último comando.
    """

    key = (
        source_node_id,
        channel_index,
    )


    last_command_time[
        key
    ] = time.monotonic()


# ============================================================
# CALLBACK MESHTASTIC
# ============================================================

def on_message(
    packet,
    interface,
):
    """
    Callback de:

        meshtastic.receive.text

    IMPORTANTE:

    Tu instalación de Meshtastic publica:

        packet=...
        interface=...

    Por eso este parámetro debe llamarse exactamente
    'interface'.

    NO cambiarlo a 'iface'.
    """

    # Alias interno.

    iface = interface


    try:

        # ====================================================
        # DEDUPLICACIÓN
        # ====================================================

        if is_duplicate_packet(
            packet
        ):

            logger.debug(
                "Paquete duplicado ignorado | "
                "id=%s",
                packet.get("id"),
            )


            return


        # ====================================================
        # DATOS DECODIFICADOS
        # ====================================================

        decoded = packet.get(
            "decoded",
            {},
        )


        if not decoded:

            return


        # ====================================================
        # TEXTO
        # ====================================================

        text = decoded.get(
            "text"
        )


        if not text:

            return


        # ====================================================
        # CANAL
        # ====================================================

        channel_index = packet.get(
            "channel",
            0,
        )


        # ====================================================
        # NODO DE ORIGEN
        # ====================================================

        source_node_id = get_source_node_id(
            packet
        )


        source_node_name = get_source_node_name(
            packet,
            iface,
        )


        # ====================================================
        # LOG DEL MENSAJE RECIBIDO
        # ====================================================

        logger.info(
            "Mensaje recibido | "
            "origen=%s | "
            "nodeNum=%s | "
            "packetId=%s | "
            "canal=%s | "
            "texto=%r",
            source_node_name,
            source_node_id,
            packet.get("id"),
            channel_index,
            text,
        )


        # ====================================================
        # COMPROBAR CANAL
        # ====================================================

        if (
            channel_index
            not in channel_indexes.values()
        ):

            logger.debug(
                "Mensaje ignorado: "
                "canal %s no está configurado.",
                channel_index,
            )


            return


        # ====================================================
        # COMPROBAR COMANDO
        # ====================================================

        if (
            text.strip().lower()
            != COMMAND.lower()
        ):

            return


        logger.info(
            "Comando %s recibido de %s",
            COMMAND,
            source_node_name,
        )


        # ====================================================
        # COOLDOWN
        # ====================================================

        if is_on_cooldown(
            source_node_id,
            channel_index,
        ):

            return


        register_command(
            source_node_id,
            channel_index,
        )


        # ====================================================
        # INFORMACIÓN DEL NODO LOCAL
        # ====================================================

        node_name = get_node_name(
            iface
        )


        # ====================================================
        # INFORMACIÓN DEL PAQUETE
        # ====================================================

        hops = get_hops(
            packet
        )


        rssi = get_rssi(
            packet
        )


        snr = get_snr(
            packet
        )


        gmt_time = get_gmt_time()


        # ====================================================
        # FORMATO RSSI
        # ====================================================

        if rssi is None:

            rssi_text = "N/D"

        else:

            rssi_text = (
                f"{rssi} dBm"
            )


        # ====================================================
        # FORMATO SNR
        # ====================================================

        if snr is None:

            snr_text = "N/D"

        else:

            snr_text = (
                f"{snr} dB"
            )


        # ====================================================
        # CREAR RESPUESTA
        # ====================================================

        response = (
            "/pong\n"
            f"Origen: {source_node_name}\n"
            f"Nodo: {node_name} | {BOT_AUTHOR}\n"
            f"Saltos: {hops}\n"
            f"Hora GMT: {gmt_time}\n"
            f"SNR: {snr_text}\n"
            f"RSSI: {rssi_text}\n"
            f"Ubicación: {LOCATION}"
        )


        # ====================================================
        # MOSTRAR MENSAJE QUE SE VA A ENVIAR
        # ====================================================

        logger.info(
            "--------------------------------------------------"
        )


        logger.info(
            "MENSAJE ENVIADO"
        )


        logger.info(
            "Destino: %s",
            source_node_name,
        )


        logger.info(
            "Canal: %s",
            channel_index,
        )


        logger.info(
            "Contenido:\n%s",
            response,
        )


        logger.info(
            "--------------------------------------------------"
        )


        # ====================================================
        # ENVIAR RESPUESTA
        # ====================================================

        iface.sendText(
            response,
            channelIndex=channel_index,
        )


        # ====================================================
        # CONFIRMACIÓN
        # ====================================================

        logger.info(
            "Respuesta enviada correctamente."
        )


    except Exception:

        logger.exception(
            "Error procesando mensaje."
        )


# ============================================================
# CONEXIÓN
# ============================================================

def connect():
    """
    Conecta al dispositivo Meshtastic.
    """

    logger.info(
        "Conectando al dispositivo Meshtastic..."
    )


    try:

        # ----------------------------------------------------
        # Puerto especificado
        # ----------------------------------------------------

        if SERIAL_PORT:

            logger.info(
                "Puerto USB: %s",
                SERIAL_PORT,
            )


            return (
                meshtastic.serial_interface
                .SerialInterface(
                    devPath=SERIAL_PORT
                )
            )


        # ----------------------------------------------------
        # Autodetección
        # ----------------------------------------------------

        logger.info(
            "Puerto USB: autodetección"
        )


        return (
            meshtastic.serial_interface
            .SerialInterface()
        )


    except Exception:

        logger.exception(
            "No se pudo conectar al "
            "dispositivo Meshtastic."
        )


        raise


# ============================================================
# MAIN
# ============================================================

def main():

    global interface
    global channel_indexes


    # ========================================================
    # LOGGING
    # ========================================================

    setup_logging()


    logger.info(
        "=========================================="
    )


    logger.info(
        "       MESHTASTIC /PING BOT"
    )


    logger.info(
        "=========================================="
    )


    logger.info(
        "Canales configurados: %s",
        ", ".join(
            CHANNEL_NAMES
        ),
    )


    logger.info(
        "Comando: %s",
        COMMAND,
    )


    logger.info(
        "Ubicación: %s",
        LOCATION,
    )


    logger.info(
        "Deduplicación: %s segundos",
        DEDUP_TTL_SECONDS,
    )


    logger.info(
        "Cooldown: %s segundos",
        COMMAND_COOLDOWN_SECONDS,
    )


    # ========================================================
    # SUSCRIPCIÓN
    # ========================================================

    pub.subscribe(
        on_message,
        "meshtastic.receive.text",
    )


    logger.info(
        "Suscrito a meshtastic.receive.text"
    )


    try:

        # ====================================================
        # CONEXIÓN
        # ====================================================

        interface = connect()


        logger.info(
            "Dispositivo conectado."
        )


        # ====================================================
        # BUSCAR CANALES
        # ====================================================

        channel_indexes = find_channels(
            interface,
            CHANNEL_NAMES,
        )


        # ====================================================
        # COMPROBAR CANALES
        # ====================================================

        missing_channels = [
            name
            for name in CHANNEL_NAMES
            if name not in channel_indexes
        ]


        if missing_channels:

            logger.error(
                "No se encontraron los siguientes "
                "canales: %s",
                ", ".join(
                    missing_channels
                ),
            )


            logger.error(
                "Comprueba que los nombres coincidan "
                "exactamente con los canales del nodo."
            )


            return 1


        # ====================================================
        # NOMBRE DEL NODO LOCAL
        # ====================================================

        node_name = get_node_name(
            interface
        )


        logger.info(
            "Nombre del nodo local: %s",
            node_name,
        )


        # ====================================================
        # INFORMACIÓN DE CANALES
        # ====================================================

        for name, index in channel_indexes.items():

            logger.info(
                'Canal "%s" encontrado en índice %s',
                name,
                index,
            )


        # ====================================================
        # ESTADO
        # ====================================================

        logger.info(
            "------------------------------------------"
        )


        logger.info(
            "BOT EJECUTÁNDOSE"
        )


        logger.info(
            "------------------------------------------"
        )


        logger.info(
            'Esperando "%s" en: %s',
            COMMAND,
            ", ".join(
                CHANNEL_NAMES
            ),
        )


        logger.info(
            "Ctrl+C para salir."
        )


        # ====================================================
        # LOOP PRINCIPAL
        # ====================================================

        while True:

            time.sleep(
                1
            )


    except KeyboardInterrupt:

        logger.info(
            "Deteniendo bot..."
        )


        return 0


    except Exception:

        logger.exception(
            "Error fatal en el bot."
        )


        return 1


    finally:

        # ====================================================
        # CERRAR CONEXIÓN
        # ====================================================

        if interface:

            try:

                interface.close()


                logger.info(
                    "Conexión cerrada."
                )


            except Exception:

                logger.exception(
                    "Error cerrando la interfaz."
                )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )