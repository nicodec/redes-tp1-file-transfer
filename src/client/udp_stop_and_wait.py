import logging
from socket import *
from message.message import DATA_MAX_SIZE, Message, MessageType, ErrorCode
from datetime import datetime, timedelta
from message.utils import send_message, send_ack, get_message_from_queue, show_info

DATA_MAX_SIZE = DATA_MAX_SIZE

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cliente_udp')


def finalizar_cliente(sock, server_addr, msg_queue, stop_event):
    """
    Finaliza la conexión con el servidor enviando un mensaje de fin y esperando un ACK.
    """
    logger.info("Iniciando proceso de finalización con el servidor.")
    end_msg = Message.end()
    while not stop_event.is_set():
        if end_msg.is_timeout():
            logger.info("Reenviando mensaje de fin al servidor.")
            send_message(end_msg, sock, server_addr)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.ACK:
            logger.info("ACK de fin recibido. Finalización completada.")
            send_ack(response.get_seq_number(), sock, server_addr)
            break


def inicio_download_client(client_socket, server_address, first_message,
                           message_queue, stop_event):
    logger.info(f'Enviando mensaje de DOWNLOAD al servidor: {first_message}')
    
    err = False
    tamanio_del_archivo = 0
    recibi_ack_o_error = False
    while not recibi_ack_o_error:
        if stop_event.is_set():
            return True, tamanio_del_archivo
        if first_message.is_timeout():
            send_message(first_message, client_socket, server_address)
        message = get_message_from_queue(message_queue)
        if message and message.get_type() == MessageType.ACK_DOWNLOAD:
            logger.info(f'El tamaño del archivo es {message.get_file_size()}')
            recibi_ack_o_error = True
            tamanio_del_archivo = message.get_file_size()
        elif message and message.get_type() == MessageType.ERROR and message.get_error_code() == ErrorCode.FILE_NOT_FOUND:
            logger.error(f'El archivo que solicite no existe en el servidor')
            recibi_ack_o_error = True
            err = True
            logger.info('Termino el inicio del DOWNLOAD')
            # inicio fin del protocolo de download(por ahora uso el de upload)
            logger.info('Proceso de fin del download')
            finalizar_cliente(client_socket, server_address, message_queue, stop_event)
            logger.info('Termino fin del download')

    return err, tamanio_del_archivo


# caso download

def download_saw_cliente(first_message, client_socket, server_address,
                         message_queue, file, filename, stop_event):
    start_time = datetime.now()
    err, tamanio_del_archivo = inicio_download_client(client_socket, server_address, first_message, message_queue, stop_event)
    
    if err:
        return
    datos_recibidos = 0
    # espero recibir el primer paquete
    recibi_el_primer_paquete = False
    ack_message = Message.ack(0)
    while not recibi_el_primer_paquete:
        if stop_event.is_set():
            return
        # envio el ack del inicio del download
        if ack_message.is_timeout():
            send_message(ack_message, client_socket, server_address)
            
        message = get_message_from_queue(message_queue)

        if message and message.get_type() == MessageType.DATA and message.get_seq_number() == 1:
            datos = message.get_data()
            recibi_el_primer_paquete = True
            logger.info('Termino el inicio del DOWNLOAD')
            logger.info('Cliente se prepara para el DOWNLOAD')
            logger.info(f'Recibo el paquete 1')

    
    ultimo_paquete_recibido = 1
    datos_recibidos = len(datos)
    file.write(datos)

    #set up progress tracking
    next_udpate = datetime.now() + timedelta(seconds=1)
    ack_message = Message.ack(ultimo_paquete_recibido)
    
    while datos_recibidos < tamanio_del_archivo:
        next_udpate = show_info(tamanio_del_archivo, datos_recibidos, start_time, next_udpate)
        
        if stop_event.is_set():
            return
        
        # Mando el ack del ultimo paquete que recibi
        if ack_message.is_timeout():
            logger.debug(f'Envio ACK {ack_message.get_seq_number()}')
            send_message(ack_message, client_socket, server_address)

        # espero y recibo el siguiente paquete
        message = get_message_from_queue(message_queue)

        if message and message.get_type() == MessageType.DATA and message.get_seq_number() == ultimo_paquete_recibido + 1:
            logger.debug(f'Recibo el paquete {message.get_seq_number()}')
            datos = message.get_data()
            file.write(datos)
            datos_recibidos = datos_recibidos + len(datos)
            ultimo_paquete_recibido = ultimo_paquete_recibido + 1
            ack_message = Message.ack(ultimo_paquete_recibido)
    
    logger.info('Se recibio el archivo con exito')

    # envio el ultimo ack del paquete recibido
    envie_ultimo_ack_del_paquete = False
    ack_message = Message.ack(ultimo_paquete_recibido)

    while not envie_ultimo_ack_del_paquete:
        if stop_event.is_set():
            return
        
        if ack_message.is_timeout():
            send_message(ack_message, client_socket, server_address)
            logger.info(f'Envio ACK {ack_message.get_seq_number()}')
        
        # espero y recibo el fin del download
        message = get_message_from_queue(message_queue)

        if message and message.get_type() == MessageType.END:
            logger.info('Recibi fin del servidor')
            envie_ultimo_ack_del_paquete = True
            
            # fin
            logger.info('Proceso de fin del download')
            finalizar_cliente(client_socket, server_address, message_queue, stop_event)
            logger.info('Termino fin del download')


