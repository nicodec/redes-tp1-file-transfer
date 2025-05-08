import hashlib
from client.udp_stop_and_wait.finalizar_cliente import (
    finalizar_cliente, finalizar_cliente_download_saw
)
from message.message import Message, MessageType, ErrorCode
from datetime import datetime, timedelta
from message.utils import send_message, get_message_from_queue, show_info
from utils.logger import logger


def inicio_download_client(client_socket, server_address,
                           first_message: Message, msg_queue, stop_event):
    err = False
    tamanio_del_archivo = 0
    recibi_ack_o_error = False
    while not recibi_ack_o_error:
        if stop_event.is_set():
            return True, tamanio_del_archivo
        if first_message.is_timeout():
            send_message(first_message, client_socket, server_address)

        message = get_message_from_queue(msg_queue)
        if message and message.get_type() == MessageType.ACK_DOWNLOAD:
            recibi_ack_o_error = True
            tamanio_del_archivo = message.get_file_size()
        elif (message and message.get_type() == MessageType.ERROR and
              message.get_error_code() == ErrorCode.FILE_NOT_FOUND):
            logger.error('El archivo que solicite no existe en el servidor')
            recibi_ack_o_error = True
            err = True
            logger.info('Termino el inicio del DOWNLOAD')
            # inicio fin del protocolo de download(por ahora uso el de upload)
            logger.info('Proceso de fin del download')
            finalizar_cliente(client_socket, server_address, msg_queue,
                              stop_event)
            logger.info('Termino fin del download')

    return err, tamanio_del_archivo


def download_saw_client(first_message, client_socket, server_address,
                        msg_queue, file, filename, stop_event):
    start_time = datetime.now()
    err, tamanio_del_archivo = inicio_download_client(
        client_socket, server_address, first_message, msg_queue, stop_event)

    if err:
        return

    datos_recibidos = 0
    ultimo_paquete_recibido = 0  # Empezamos en 0, esperando el paquete 1
    next_update = datetime.now() + timedelta(seconds=1)
    ack_message = Message.ack(ultimo_paquete_recibido)

    while datos_recibidos < tamanio_del_archivo:
        next_update = show_info(
            tamanio_del_archivo, datos_recibidos, start_time, next_update)

        if stop_event.is_set():
            return

        # Mando el ack del ultimo paquete que recibi si es necesario
        if ack_message.is_timeout():
            logger.debug(f'Envio ACK {ack_message.get_seq_number()}')
            send_message(ack_message, client_socket, server_address)

        # espero y recibo el siguiente paquete
        message = get_message_from_queue(msg_queue)

        # Caso de retransmisión de ACK para un paquete anterior (duplicado)
        if (message and message.get_type() == MessageType.DATA and
                message.get_seq_number() < ultimo_paquete_recibido + 1):
            logger.debug(f"Recibi paquete duplicado "
                         f"{message.get_seq_number()}, reenvio ACK")
            ack_message = Message.ack(message.get_seq_number())
            send_message(ack_message, client_socket, server_address)

        # Caso de recepción del paquete esperado
        elif (message and message.get_type() == MessageType.DATA and
              message.get_seq_number() == ultimo_paquete_recibido + 1):
            logger.debug(f'Recibo el paquete {message.get_seq_number()}')
            datos = message.get_data()
            file.write(datos)
            datos_recibidos = datos_recibidos + len(datos)
            ultimo_paquete_recibido = ultimo_paquete_recibido + 1
            ack_message = Message.ack(ultimo_paquete_recibido)
            send_message(ack_message, client_socket, server_address)

    # envio el ultimo ack del paquete recibido
    envie_ultimo_ack_del_paquete = False
    ack_message = Message.ack(ultimo_paquete_recibido)

    while not envie_ultimo_ack_del_paquete:
        if stop_event.is_set():
            return

        if ack_message.is_timeout():
            send_message(ack_message, client_socket, server_address)

        # espero y recibo el fin del download
        message = get_message_from_queue(msg_queue)

        if message and message.get_type() == MessageType.END:
            envie_ultimo_ack_del_paquete = True

            file.flush()  # Sin esto no funciona el digest
            file_read_for_digest: bytes
            with open(filename, 'rb') as file_read_for_digest:
                file_read_for_digest = file_read_for_digest.read()
            final_md5_digest = hashlib.md5(file_read_for_digest).hexdigest()

            # fin
            finalizar_cliente_download_saw(
                client_socket, server_address, msg_queue, stop_event,
                final_md5_digest, filename)
