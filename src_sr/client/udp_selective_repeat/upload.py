from datetime import datetime, timedelta
import os

from message.message import TOTAL_BYTES_LENGTH, DATA_MAX_SIZE, Message, MessageType
from message.utils import send_message, show_info
from utils.protocol_utils import (
    send_first_ack_download_message,
    read_file,
    init_window,
    has_errors,
    send_error_message,
    send_first_upload_message,
    end_send_protocol
)
from utils.logger import logger


def upload_sr_client(initial_message, socket, address, message_queue, file, stop_event):
    start_time = datetime.now()
    logger.debug(f"El mensaje al entrar es : {initial_message}")
    
    first_message_recv = None
    if initial_message.get_type() == MessageType.UPLOAD: 
        first_message_recv = send_first_upload_message(initial_message, socket, address, message_queue, stop_event)
    elif initial_message.get_type() == MessageType.ERROR:
        first_message_recv = send_error_message(initial_message, socket, address, message_queue, stop_event, MessageType.UPLOAD)
    elif initial_message.get_type() == MessageType.ACK_DOWNLOAD:
        first_message_recv = send_first_ack_download_message(initial_message, socket, address, message_queue, stop_event)
    if has_errors(first_message_recv, initial_message):
        return
    
    if has_errors(first_message_recv, initial_message):
        return
    
    package_to_send_size, window_base, window_top = init_window(initial_message)
    acknowledgements = [False] * package_to_send_size
    sended_messages = [None] * package_to_send_size
    received_acknowledgements = 0
    logger.debug(f"Packages to send: {package_to_send_size} and window_base {window_base} and window_top {window_top}")

    next_update = datetime.now() + timedelta(seconds=1)
    while received_acknowledgements < package_to_send_size:
        next_update = show_info(package_to_send_size * TOTAL_BYTES_LENGTH, received_acknowledgements * TOTAL_BYTES_LENGTH, start_time, next_update)
        if stop_event.is_set():
            return
        #send window
        for i in range(window_base, window_top):
            if (not sended_messages[i] and not acknowledgements[i]):
                logger.debug(f"i : {i} and {acknowledgements[i]}")
                sended_messages[i] = Message.data(i, read_file(file, DATA_MAX_SIZE, i))
                send_message(sended_messages[i], socket, address)
            if (sended_messages[i] and sended_messages[i].is_timeout() and not acknowledgements[i]):
                send_message(sended_messages[i], socket, address)
    
        message = message_queue.get(False) if not message_queue.empty() else None
        if message:
            if message.get_type() == MessageType.ACK:
                seqNumber = message.get_seq_number()
                logger.debug(f"Received ack {seqNumber}")
                if not acknowledgements[seqNumber]:
                    acknowledgements[seqNumber] = True
                    received_acknowledgements += 1

                    #move window
                    while acknowledgements[window_base]:
                        if (window_base + 1) < package_to_send_size:
                            window_base += 1
                            if (window_top) < package_to_send_size:
                                window_top += 1
                        else:
                            break
            elif message.get_type() == MessageType.ERROR:
                logger.error(f"Error enviando datos -- {message.getErrorCode}" )
                return
    logger.info(f"El archivo se ha enviado correctamente.")
    end_send_protocol(message_queue, socket, address, stop_event)