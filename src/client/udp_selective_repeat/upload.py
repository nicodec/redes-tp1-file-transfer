from datetime import datetime, timedelta
from message.message import TOTAL_BYTES_LENGTH, DATA_MAX_SIZE, Message, MessageType, ErrorCode
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


def read_file(file, chunk_size, offset):
    """Reads a chunk of data from a file at the specified offset."""
    real_offset = offset * chunk_size
    logger.debug(f"Reading file... offset is: {real_offset}")
    file.seek(real_offset)
    return file.read(chunk_size)


def inicio_upload_client(client_socket, server_address, first_message,
                         message_queue, file_size, stop_event):
    """Inicia el proceso de carga enviando información del archivo."""
    logger.info(f'Enviando mensaje de UPLOAD al servidor: {first_message}')
    
    err = False
    recibi_ack_o_error = False
    
    while not recibi_ack_o_error:
        if stop_event.is_set():
            return True
        
        if first_message.is_timeout():
            send_message(first_message, client_socket, server_address)
            
        message = get_message_from_queue(message_queue)
        
        if message and message.get_type() == MessageType.ACK:
            logger.info(f'El servidor está listo para recibir el archivo')
            recibi_ack_o_error = True
            
        elif message and message.get_type() == MessageType.ERROR:
            logger.error(f'Error en el servidor: {message.get_error_code()}')
            if message.get_error_code() == ErrorCode.FILE_ALREADY_EXISTS:
                logger.error("El archivo ya existe en el servidor")
            elif message.get_error_code() == ErrorCode.FILE_TOO_BIG:
                logger.error("El archivo es muy grande, no se puede cargar")
            
            recibi_ack_o_error = True
            err = True
            logger.info('Termino el inicio del UPLOAD')
            finalizar_cliente(client_socket, server_address, message_queue, stop_event)
            logger.info('Termino fin del upload')

    return err


def upload_sr_client(first_message, client_socket, server_address,
                                  message_queue, file, stop_event):
    """Implementa el protocolo Selective Repeat para la carga de archivos."""
    start_time = datetime.now()
    file_size = first_message.get_file_size()
    
    # Iniciar el proceso de carga
    err = inicio_upload_client(client_socket, server_address, first_message,
                              message_queue, file_size, stop_event)
    
    if err:
        return
    
    # Inicializar la ventana deslizante
    package_to_send_size, window_base, window_top = init_window(file_size)
    acknowledgements = [False] * package_to_send_size
    sended_messages = [None] * package_to_send_size
    received_acknowledgements = 0
    
    # Enviar el archivo usando ventana deslizante
    next_update = datetime.now() + timedelta(seconds=1)
    
    while received_acknowledgements < package_to_send_size:
        next_update = show_info(package_to_send_size * TOTAL_BYTES_LENGTH, 
                               received_acknowledgements * TOTAL_BYTES_LENGTH, 
                               start_time, next_update)
        
        if stop_event.is_set():
            return
            
        # Enviar paquetes en la ventana actual
        for i in range(window_base, window_top):
            if not acknowledgements[i]:
                if not sended_messages[i]:
                    # Crear y enviar nuevo paquete
                    data = read_file(file, DATA_MAX_SIZE, i)
                    if data:  # Asegurar que hay datos para enviar
                        sended_messages[i] = Message.data(i, data)
                        send_message(sended_messages[i], client_socket, server_address)
                        logger.debug(f"Enviado paquete {i}")
                elif sended_messages[i].is_timeout():
                    # Reenviar paquete por timeout
                    send_message(sended_messages[i], client_socket, server_address)
                    logger.debug(f"Reenviando paquete {i} por timeout")
        
        # Procesar ACKs recibidos
        response = get_message_from_queue(message_queue)
        if response and response.get_type() == MessageType.ACK:
            seq_number = response.get_seq_number()
            
            if 0 <= seq_number < package_to_send_size and not acknowledgements[seq_number]:
                logger.debug(f"ACK recibido para el paquete {seq_number}")
                acknowledgements[seq_number] = True
                received_acknowledgements += 1
                
                # Avanzar la ventana si es posible
                while window_base < package_to_send_size and acknowledgements[window_base]:
                    window_base += 1
                    if window_top < package_to_send_size:
                        window_top += 1
                    logger.debug(f"Ventana avanzada a base={window_base}, top={window_top}")
    
    logger.info("Archivo enviado completamente.")
    
    # Finalizar la transferencia
    end_send_protocol(message_queue, client_socket, server_address, stop_event)


def end_send_protocol(message_queue, client_socket, server_address, stop_event):
    """Finaliza el protocolo de envío enviando mensaje de fin."""
    logger.info("Finalizando la transferencia")
    end_message = Message.end()
    send_message(end_message, client_socket, server_address)
    
    fin_enviado = False
    while not fin_enviado:
        if stop_event.is_set():
            return
            
        if end_message.is_timeout():
            logger.debug("Reenviando mensaje de fin al servidor.")
            send_message(end_message, client_socket, server_address)
            
        response = get_message_from_queue(message_queue)
        
        if response and response.get_type() == MessageType.ACK_END:
            logger.info("ACK de fin recibido del servidor.")
            ack_message = Message.ack(response.get_seq_number())
            send_message(ack_message, client_socket, server_address)
            fin_enviado = True
            finalizar_cliente(client_socket, server_address, message_queue, stop_event)
            logger.info("Proceso de carga finalizado")