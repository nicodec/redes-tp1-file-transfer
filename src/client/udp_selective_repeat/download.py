from datetime import datetime, timedelta
import os
from message.message import TOTAL_BYTES_LENGTH, DATA_MAX_SIZE, Message, MessageType
from message.utils import send_message, get_message_from_queue, show_info
from client.udp_stop_and_wait.finalizar_cliente import finalizar_cliente
from utils.logger import logger


def init_window(file_size):
    """Initializes the sliding window parameters for selective repeat."""
    package_amount = (file_size // DATA_MAX_SIZE) + 1
    window_base = 0
    window_top = 1 if package_amount < 2 else package_amount // 2
    logger.debug(f"package_amount: {package_amount}, window_base: {window_base}, window_top: {window_top}")
    return package_amount, window_base, window_top


def inicio_download_client(client_socket, server_address, first_message,
                           message_queue, stop_event):
    """Initiates the download process by sending the download request and receiving file information."""
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
            
        elif message and message.get_type() == MessageType.ERROR:
            logger.error(f'El archivo que solicité no existe en el servidor')
            recibi_ack_o_error = True
            err = True
            logger.info('Termino el inicio del DOWNLOAD')
            # Finalizo el protocolo de download al detectar error
            finalizar_cliente(client_socket, server_address, message_queue, stop_event)
            logger.info('Termino fin del download')

    return err, tamanio_del_archivo


def download_sr_client(first_message, client_socket, server_address,
                                     message_queue, file, filename, stop_event):
    """Implements the selective repeat protocol for downloading files."""
    start_time = datetime.now()
    
    # Iniciar el proceso de descarga
    err, tamanio_del_archivo = inicio_download_client(client_socket, server_address, first_message, message_queue, stop_event)
    
    if err:
        return
    
    # Inicializo la ventana
    package_to_receive_size, window_base, window_top = init_window(tamanio_del_archivo)
    received_messages = [False] * package_to_receive_size
    received_data = [''] * package_to_receive_size
    received_packages = 0
    
    # Envío ACK inicial para comenzar la recepción de datos
    ack_message = Message.ack(0)
    send_message(ack_message, client_socket, server_address)
    logger.info("ACK inicial enviado. Preparando para recibir archivo.")
    
    # Recibir paquetes de datos
    next_update = datetime.now() + timedelta(seconds=1)
    
    while received_packages < package_to_receive_size:
        next_update = show_info(package_to_receive_size * TOTAL_BYTES_LENGTH, received_packages * TOTAL_BYTES_LENGTH, start_time, next_update)
        
        if stop_event.is_set():
            if os.path.exists(filename):
                os.unlink(filename)
            return
        
        message = get_message_from_queue(message_queue)
        
        if message:
            if message.get_type() == MessageType.DATA:
                seq_number = message.get_seq_number()
                
                # Verificar si el paquete está dentro de la ventana
                if window_base <= seq_number < window_top:
                    if not received_messages[seq_number]:
                        received_messages[seq_number] = True
                        received_data[seq_number] = message.get_data()
                        received_packages += 1
                        logger.debug(f"Recibido paquete {seq_number}, total recibidos: {received_packages}")
                    
                    # Enviar ACK para este paquete
                    ack_message = Message.ack(seq_number)
                    send_message(ack_message, client_socket, server_address)
                    logger.debug(f"Enviado ACK para paquete {seq_number}")
                    
                    # Avanzar la ventana si es posible
                    while received_messages[window_base]:
                        file.write(received_data[window_base])
                        window_base += 1
                        if window_top < package_to_receive_size:
                            window_top += 1
                        if window_base >= package_to_receive_size:
                            break
                
                # Si el paquete está antes de la ventana, aún así enviar ACK
                elif seq_number < window_base:
                    ack_message = Message.ack(seq_number)
                    send_message(ack_message, client_socket, server_address)
                    logger.debug(f"Enviado ACK para paquete {seq_number} (duplicado)")
            
            elif message.get_type() == MessageType.END:
                logger.info("Recibido mensaje de fin de la transferencia")
                break
                
            elif message.get_type() == MessageType.ERROR:
                logger.error(f"Error en la descarga")
                if os.path.exists(filename):
                    os.unlink(filename)
                return
    
    logger.info("Archivo recibido completamente")
    
    # Finalizar la transferencia
    end_recv_protocol(message_queue, client_socket, server_address, stop_event)


def end_recv_protocol(message_queue, client_socket, server_address, stop_event):
    """Finaliza el protocolo de recepción confirmando el fin de la transferencia."""
    logger.info("Finalizando la transferencia")
    ack_end_message = Message.ack_end(0)  # Usamos 0 como número de secuencia para el mensaje de fin
    send_message(ack_end_message, client_socket, server_address)
    
    fin_recibido = False
    while not fin_recibido:
        if stop_event.is_set():
            logger.warning("No se ha podido confirmar el mensaje de fin de conexión.")
            return
        
        if ack_end_message.is_timeout():
            send_message(ack_end_message, client_socket, server_address)
            
        message = get_message_from_queue(message_queue)
        
        if message and message.get_type() == MessageType.ACK:
            logger.debug("Se ha cerrado la conexión correctamente")
            fin_recibido = True
            finalizar_cliente(client_socket, server_address, message_queue, stop_event)
            logger.info("Proceso de descarga finalizado")