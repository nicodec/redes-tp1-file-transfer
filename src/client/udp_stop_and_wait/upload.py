from client.udp_stop_and_wait.finalizar_cliente import finalizar_cliente
from message.message import DATA_MAX_SIZE, Message, MessageType, ErrorCode
from datetime import datetime, timedelta
from message.utils import (
    send_message, send_ack, get_message_from_queue, show_info
)
from utils.logger import logger


def inicio_upload_client(client_socket, server_address,
                         mensaje_inicial: Message, msg_queue, stop_event):
    """Inicia el protocolo de subida enviando el mensaje inicial y
    manejando errores."""
    ack_o_error_recibido = False

    while not ack_o_error_recibido:
        if stop_event.is_set():
            return True
        if mensaje_inicial.is_timeout():
            logger.debug("Reenviando mensaje de inicio de upload.")
            send_message(mensaje_inicial, client_socket, server_address)

        respuesta = get_message_from_queue(msg_queue)
        if respuesta:
            # Manejo de errores
            if respuesta.get_type() == MessageType.ERROR:
                error_code = respuesta.get_error_code()
                if error_code == ErrorCode.FILE_TOO_BIG:
                    logger.error("El archivo es demasiado grande para ser"
                                 "subido.")
                elif error_code == ErrorCode.FILE_ALREADY_EXISTS:
                    logger.error("El archivo ya existe en el servidor.")
                ack_o_error_recibido = True
                logger.info("Finalizando el protocolo de upload debido a un "
                            "error.")
                finalizar_cliente(client_socket, server_address, msg_queue,
                                  stop_event)
                return True

            # Caso de ACK recibido
            if (respuesta.get_type() == MessageType.ACK and
                    respuesta.get_seq_number() == 0):
                send_ack(respuesta.get_seq_number(), client_socket,
                         server_address)
                ack_o_error_recibido = True

    return False


def upload_saw_client(mensaje_inicial: Message, client_socket, server_address,
                      msg_queue, archivo, stop_event):
    """Implementa el protocolo Stop-and-Wait para la subida de archivos."""
    inicio = datetime.now()
    error_detectado = inicio_upload_client(
        client_socket, server_address, mensaje_inicial, msg_queue, stop_event)

    if error_detectado:
        return

    siguiente_actualizacion = inicio + timedelta(seconds=1)
    secuencia = 1
    bytes_enviados = 0

    while datos := archivo.read(DATA_MAX_SIZE):
        siguiente_actualizacion = show_info(
            mensaje_inicial.get_file_size(), bytes_enviados, inicio,
            siguiente_actualizacion)
        ack_recibido = False

        if stop_event.is_set():
            return

        paquete = Message.data(secuencia, datos)
        while not ack_recibido:
            if stop_event.is_set():
                return
            if paquete.is_timeout():
                logger.debug(f"Reenviando paquete {secuencia}.")
                send_message(paquete, client_socket, server_address)

            respuesta = get_message_from_queue(msg_queue)
            if (respuesta and respuesta.get_type() == MessageType.ACK and
                    respuesta.get_seq_number() == secuencia):
                logger.debug(f"ACK recibido para el paquete {secuencia}.")
                bytes_enviados += len(datos)
                secuencia += 1
                ack_recibido = True

    finalizar_cliente(client_socket, server_address, msg_queue, stop_event)
