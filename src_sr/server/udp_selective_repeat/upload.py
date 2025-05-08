from datetime import datetime, timedelta
import hashlib
import os
import threading

from message.message import TOTAL_BYTES_LENGTH, ErrorCode, Message, MessageType
from message.utils import send_ack, show_info
from utils.protocol_utils import (
    end_recv_protocol_on_error,
    send_first_ack_message,
    init_window,
    has_errors,
    send_error_message,
    send_first_download_message,
    end_recv_protocol,
    recv_data_message
)
from utils.logger import logger


def upload_sr_server(initial_message, socket, address, message_queue, file, filename, msg_md5_digest, stop_event):
    start_time = datetime.now()
    logger.debug(f"El mensaje al entrar es : {initial_message}")
    
    first_message_recv = None
    if initial_message.get_type() == MessageType.ERROR:
        first_message_recv = send_error_message(initial_message, socket, address, message_queue, stop_event, MessageType.DOWNLOAD)
    elif initial_message.get_type() == MessageType.DOWNLOAD:
        first_message_recv, initial_message = send_first_download_message(initial_message, socket, address, message_queue, stop_event)
    elif initial_message.get_type() == MessageType.UPLOAD:
        first_message_recv = send_first_ack_message(Message.ack(initial_message.get_seq_number()), socket, address, message_queue, stop_event)
    
    if has_errors(first_message_recv, initial_message):
        return
    
    # Inicializo ventana
    package_to_receive_size, window_base, window_top = init_window(initial_message)
    received_messages = [False] * package_to_receive_size
    received_data = [''] * package_to_receive_size
    received_packages = 0
    logger.debug(f"Window_base {window_base} and window_top {window_top}")

    if first_message_recv.get_type() == MessageType.DATA:
        window_base, window_top, received_packages = recv_data_message(first_message_recv, socket, address, received_messages, received_data, package_to_receive_size, window_base, window_top, received_packages, file)
    
    next_update = datetime.now() + timedelta(seconds=1)
    timeout = datetime.now() + timedelta(seconds=15)
    while True and timeout > datetime.now():
        next_update = show_info(package_to_receive_size * TOTAL_BYTES_LENGTH, received_packages * TOTAL_BYTES_LENGTH, start_time, next_update)
        if stop_event.is_set():
            os.unlink(filename)
            return
        
        message = message_queue.get(False) if not message_queue.empty() else None
        if message:
            timeout = datetime.now() + timedelta(seconds=15)
            if message.get_type() == MessageType.DATA:
                window_base, window_top, received_packages = recv_data_message(message, socket, address, received_messages, received_data, package_to_receive_size, window_base, window_top, received_packages, file)
            elif message.get_type() == MessageType.END:
                file.flush() # Sin esto rompe el md5
                
                file_read_for_digest: bytes
                with open(filename, 'rb') as file_read_for_digest:
                    file_read_for_digest = file_read_for_digest.read()
                final_md5_digest = hashlib.md5(file_read_for_digest).hexdigest()
                
                if final_md5_digest == msg_md5_digest:
                    logger.debug("archivo recibido integramente")
                    end_recv_protocol(message_queue, message, socket, address, stop_event)
                else:
                    logger.error("Error en la integrad del archivo.")
                    os.unlink(filename)
                    end_recv_protocol_on_error(message_queue, message, socket, address, stop_event)                    
                return
            elif message.get_type() == MessageType.ERROR:
                logger.error(f"Error en la descarga -- {message.getErrorCode}" )
                send_ack(message.get_seq_number(), socket, address)
                return
    logger.error(f"Timeout. Archivo temporal borrado. Conexion cerrada para {threading.get_native_id()}")
    os.unlink(filename)