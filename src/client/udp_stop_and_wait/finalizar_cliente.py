import os
from message.message import Message, MessageType
from message.utils import send_message, send_ack, get_message_from_queue
from utils.logger import logger


def finalizar_cliente(sock, server_addr, msg_queue, stop_event):
    """
    Finaliza la conexión con el servidor enviando un mensaje de fin y esperando
    un ACK.
    """
    end_msg = Message.end()
    while not stop_event.is_set():
        if end_msg.is_timeout():
            send_message(end_msg, sock, server_addr)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.ACK:
            if (response.get_seq_number() == 1):
                logger.error("El archivo no se ha subido integramente. Por "
                             "favor intente nuevamente")
            send_ack(response.get_seq_number(), sock, server_addr)
            break


def finalizar_cliente_download_saw(sock, server_addr, msg_queue, stop_event,
                                   final_md5_digest, filename):
    """
    Finaliza la conexión con el servidor enviando un mensaje de fin y esperando
    un ACK.
    """
    end_msg = Message.end()
    while not stop_event.is_set():
        if end_msg.is_timeout():
            send_message(end_msg, sock, server_addr)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.ACK:
            md5_digest = response.get_data_as_string()
            if (final_md5_digest != md5_digest):
                logger.error("Error en la integridad del archivo. Por favor, "
                             "descarguelo nuevamente.")
                os.unlink(filename)
            send_ack(response.get_seq_number(), sock, server_addr)
            break
