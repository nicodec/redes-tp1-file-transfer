from datetime import datetime, timedelta
from server.udp_stop_and_wait.finalizar_servidor import finalizar_servidor
from message.message import TOTAL_BYTES_LENGTH, DATA_MAX_SIZE, Message, MessageType, ErrorCode
from message.utils import send_message, get_message_from_queue, show_info
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


def inicio_download_server(sock, client_address, first_message, msg_queue, stop_event):
    """Inicia el proceso de descarga verificando errores y enviando el tamaño del archivo."""
    logger.info("Iniciando protocolo de descarga (Selective Repeat).")
    error_detectado = False

    # Caso de error: archivo no encontrado
    if first_message.get_type() == MessageType.ERROR:
        error_detectado = True
        logger.error("El archivo solicitado no existe.")
        while not stop_event.is_set():
            if first_message.is_timeout():
                send_message(first_message, sock, client_address)
            response = get_message_from_queue(msg_queue)
            if response and response.get_type() == MessageType.ACK:
                logger.info("Cliente finalizó el proceso de descarga.")
                finalizar_servidor(sock, client_address, msg_queue, stop_event)
                break

    return error_detectado


def download_sr_server(first_message, sock,
                                    client_address, msg_queue,
                                    file, stop_event):
    """Implementa el protocolo Selective Repeat para la descarga de archivos."""
    start_time = datetime.now()
    error_detectado = inicio_download_server(sock, client_address, first_message, msg_queue, stop_event)

    if error_detectado:
        return

    file_size = first_message.get_file_size()
    logger.info(f"Tamaño del archivo: {file_size} bytes.")
    
    # Esperar el ACK inicial del cliente
    ack_recibido = False
    while not ack_recibido:
        if stop_event.is_set():
            return
        if first_message.is_timeout():
            logger.debug(f"Reenviando ACK inicial al cliente {client_address}.")
            send_message(first_message, sock, client_address)
            
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.ACK and response.get_seq_number() == 0:
            ack_recibido = True
            logger.info("ACK inicial recibido. Preparando envío del archivo.")

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
                        send_message(sended_messages[i], sock, client_address)
                        logger.debug(f"Enviado paquete {i}")
                elif sended_messages[i].is_timeout():
                    # Reenviar paquete por timeout
                    send_message(sended_messages[i], sock, client_address)
                    logger.debug(f"Reenviando paquete {i} por timeout")
        
        # Procesar ACKs recibidos
        response = get_message_from_queue(msg_queue)
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
    end_send_protocol(msg_queue, sock, client_address, stop_event)


def end_send_protocol(msg_queue, sock, client_address, stop_event):
    """Finaliza el protocolo de envío enviando mensaje de fin."""
    logger.info("Finalizando la transferencia")
    end_message = Message.end()
    send_message(end_message, sock, client_address)
    
    fin_enviado = False
    while not fin_enviado:
        if stop_event.is_set():
            return
            
        if end_message.is_timeout():
            logger.debug("Reenviando mensaje de fin al cliente.")
            send_message(end_message, sock, client_address)
            
        response = get_message_from_queue(msg_queue)
        
        if response and response.get_type() == MessageType.ACK_END:
            logger.info("ACK de fin recibido del cliente.")
            ack_message = Message.ack(response.get_seq_number())
            send_message(ack_message, sock, client_address)
            fin_enviado = True
            finalizar_servidor(sock, client_address, msg_queue, stop_event)
            logger.info("Proceso de descarga finalizado")