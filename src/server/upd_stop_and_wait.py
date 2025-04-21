from datetime import datetime, timedelta
import logging
from message.message import DATA_MAX_SIZE, Message, MessageType
from message.utils import send_message, send_ack, get_message_from_queue, show_info
import os

DATA_MAX_SIZE = DATA_MAX_SIZE

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cliente_udp')

def finalizar_servidor(sock, client_address, msg_queue, stop_event):
    """Finaliza la conexión con el cliente enviando un ACK al recibir un mensaje END."""
    logger.info("Iniciando proceso de finalización con el cliente.")
    ack_message = Message.ack(0)  # Crear un mensaje ACK

    while not stop_event.is_set():
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.END:
            logger.info("Mensaje END recibido. Enviando ACK al cliente.")
            send_message(ack_message, sock, client_address)  # Enviar el ACK
            break
        elif ack_message.is_timeout():
            logger.info("Reenviando ACK al cliente.")
            send_message(ack_message, sock, client_address)


def inicio_download_server(sock, client_address, first_message, msg_queue, stop_event):
    """Inicia el proceso de descarga verificando errores y enviando el tamaño del archivo."""
    logger.info("Iniciando protocolo de descarga.")
    error_detectado = False

    # Caso de error: archivo no encontrado
    if first_message.get_type() == MessageType.ERROR:
        error_detectado = True
        logger.error("El archivo solicitado no existe.")
        while not stop_event.is_set():
            if first_message.is_timeout():
                send_message(first_message, sock, client_address)
            response = get_message_from_queue(msg_queue)
            if response and response.get_type() == MessageType.END:
                logger.info("Cliente finalizó el proceso de descarga.")
                finalizar_servidor(sock, client_address, msg_queue, stop_event)
                break

    return error_detectado


def download_saw_server(first_message, sock, client_address, msg_queue, file, filename, stop_event):
    """Implementa el protocolo Stop-and-Wait para la descarga de archivos."""
    start_time = datetime.now()
    error_detectado = inicio_download_server(sock, client_address, first_message, msg_queue, stop_event)

    if error_detectado:
        return

    logger.info(f"Tamaño del archivo: {first_message.get_file_size()} bytes.")
    ack_recibido = False

    # Esperar el ACK inicial del cliente
    while not ack_recibido:
        if stop_event.is_set():
            return
        if first_message.is_timeout():
            logger.debug(f"Reenviando ACK inicial al cliente {client_address}.")
            send_message(first_message, sock, client_address)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.ACK:
            ack_recibido = True
            logger.info("ACK inicial recibido. Preparando envío del archivo.")

    # Enviar el archivo en paquetes
    next_update = start_time + timedelta(seconds=1)
    paquete_actual = 1
    while data := file.read(DATA_MAX_SIZE):
        next_update = show_info(first_message.get_file_size(), paquete_actual * DATA_MAX_SIZE, start_time, next_update)
        ack_recibido = False
        paquete = Message.data(paquete_actual, data)

        while not ack_recibido:
            if stop_event.is_set():
                return
            if paquete.is_timeout():
                logger.debug(f"Reenviando paquete {paquete_actual}.")
                send_message(paquete, sock, client_address)
            response = get_message_from_queue(msg_queue)
            if response and response.get_type() == MessageType.ACK and response.get_seq_number() == paquete_actual:
                logger.debug(f"ACK recibido para el paquete {paquete_actual}.")
                ack_recibido = True
                paquete_actual += 1

    logger.info("Archivo enviado con éxito.")

    # Finalizar la transferencia
    fin_enviado = False
    end_message = Message.end()
    while not fin_enviado:
        if stop_event.is_set():
            return
        if end_message.is_timeout():
            logger.debug("Reenviando mensaje de fin al cliente.")
            send_message(end_message, sock, client_address)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.END:
            logger.info("Fin del cliente recibido.")
            fin_enviado = True
            finalizar_servidor(sock, client_address, msg_queue, stop_event)
            logger.info("Proceso de descarga finalizado.")