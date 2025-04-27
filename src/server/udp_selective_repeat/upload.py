from datetime import datetime, timedelta
import os
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


def inicio_upload_server(sock, client_address, first_message, msg_queue, stop_event, filename):
    """Inicia el proceso de carga verificando errores y enviando confirmación."""
    logger.info("Iniciando protocolo de carga (Selective Repeat).")
    error_detectado = False
    error_message = None
    
    # Enviar respuesta (ACK o ERROR)
    if error_detectado:
        while not stop_event.is_set():
            if error_message.is_timeout():
                send_message(error_message, sock, client_address)
            response = get_message_from_queue(msg_queue)
            if response and response.get_type() == MessageType.ACK:
                logger.info("Cliente finalizó el proceso de carga después del error.")
                finalizar_servidor(sock, client_address, msg_queue, stop_event)
                break
    else:
        # Enviar ACK para iniciar la transferencia
        ack_message = Message.ack(first_message.get_seq_number())
        send_message(ack_message, sock, client_address)
        logger.info(f"ACK enviado para iniciar transferencia. Tamaño del archivo: {first_message.get_file_size()} bytes.")
    
    return error_detectado


def upload_sr_server(first_message, sock,
                                  client_address, msg_queue,
                                  file, filename, stop_event):
    """Implementa el protocolo Selective Repeat para la recepción de archivos."""
    start_time = datetime.now()
    file_size = first_message.get_file_size()
    
    # Iniciar el proceso de carga
    error_detectado = inicio_upload_server(sock, client_address, first_message, msg_queue, stop_event, filename)
    
    if error_detectado:
        return
    
    # Inicializar la ventana deslizante
    package_to_receive_size, window_base, window_top = init_window(file_size)
    received_messages = [False] * package_to_receive_size
    received_data = [''] * package_to_receive_size
    received_packages = 0
    
    # Recibir paquetes de datos
    next_update = datetime.now() + timedelta(seconds=1)
    
    while received_packages < package_to_receive_size:
        next_update = show_info(package_to_receive_size * TOTAL_BYTES_LENGTH, 
                               received_packages * TOTAL_BYTES_LENGTH, 
                               start_time, next_update)
        
        if stop_event.is_set():
            if os.path.exists(filename):
                os.unlink(filename)
            return
        
        message = get_message_from_queue(msg_queue)
        
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
                    send_message(ack_message, sock, client_address)
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
                    send_message(ack_message, sock, client_address)
                    logger.debug(f"Enviado ACK para paquete {seq_number} (duplicado)")
            
            elif message.get_type() == MessageType.END:
                logger.info("Recibido mensaje de fin de la transferencia")
                break
    
    logger.info("Archivo recibido completamente")
    
    # Finalizar la transferencia
    end_recv_protocol(msg_queue, sock, client_address, stop_event)


def end_recv_protocol(msg_queue, sock, client_address, stop_event):
    """Finaliza el protocolo de recepción confirmando el fin de la transferencia."""
    logger.info("Finalizando la transferencia")
    ack_end_message = Message.ack_end(0)  # Usamos 0 como número de secuencia para el mensaje de fin
    send_message(ack_end_message, sock, client_address)
    
    fin_recibido = False
    while not fin_recibido:
        if stop_event.is_set():
            logger.warning("No se ha podido confirmar el mensaje de fin de conexión.")
            return
        
        if ack_end_message.is_timeout():
            send_message(ack_end_message, sock, client_address)
            
        message = get_message_from_queue(msg_queue)
        
        if message and message.get_type() == MessageType.ACK:
            logger.debug("Se ha cerrado la conexión correctamente")
            fin_recibido = True
            finalizar_servidor(sock, client_address, msg_queue, stop_event)
            logger.info("Proceso de carga finalizado")