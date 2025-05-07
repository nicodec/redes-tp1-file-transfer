from datetime import datetime, timedelta
import hashlib
import os

from message.message import TOTAL_BYTES_LENGTH, Message, MessageType
from message.utils import send_ack, show_info
from utils.protocol_utils import (
    send_first_ack_message,
    send_first_download_message,
    init_window,
    has_errors,
    send_error_message,
    end_recv_protocol,
    recv_data_message,
)
from utils.logger import logger


def download_sr_client(initial_message: Message, socket, address,
                       message_queue, file, filename, stop_event):
    start_time = datetime.now()
    logger.debug(f"El mensaje al entrar es : {initial_message}")

    first_message_recv = None
    if initial_message.get_type() == MessageType.ERROR:
        first_message_recv = send_error_message(
            initial_message, socket, address, message_queue, stop_event,
            MessageType.DOWNLOAD)
    elif initial_message.get_type() == MessageType.DOWNLOAD:
        first_message_recv, initial_message = send_first_download_message(
            initial_message, socket, address, message_queue, stop_event)
    elif initial_message.get_type() == MessageType.UPLOAD:
        first_message_recv = send_first_ack_message(
            Message.ack(initial_message.get_seq_number()), socket, address,
            message_queue, stop_event)

    if has_errors(first_message_recv, initial_message):
        return

    # Inicializo ventana
    package_to_receive_size, window_base, window_top = init_window(
        initial_message)
    received_messages = [False] * package_to_receive_size
    received_data = [''] * package_to_receive_size
    received_packages = 0
    logger.debug(f"Window_base {window_base} and window_top {window_top}")

    if first_message_recv.get_type() == MessageType.DATA:
        window_base, window_top, received_packages = recv_data_message(
            first_message_recv, socket, address, received_messages,
            received_data, package_to_receive_size, window_base, window_top,
            received_packages, file)

    next_update = datetime.now() + timedelta(seconds=1)
    while True:
        next_update = show_info(package_to_receive_size * TOTAL_BYTES_LENGTH,
                                received_packages * TOTAL_BYTES_LENGTH,
                                start_time, next_update)
        if stop_event.is_set():
            os.unlink(filename)
            return

        message = (message_queue.get(False) if not message_queue.empty()
                   else None)
        if message:
            if message.get_type() == MessageType.DATA:
                window_base, window_top, received_packages = recv_data_message(
                    message, socket, address, received_messages, received_data,
                    package_to_receive_size, window_base, window_top,
                    received_packages, file)
            elif message.get_type() == MessageType.END:
                md5_digest = message.get_data_as_string()

                file.flush()  # Sin esto no funciona el digest
                file_read_for_digest: bytes
                with open(filename, 'rb') as file_read_for_digest:
                    file_read_for_digest = file_read_for_digest.read()
                final_md5_digest = hashlib.md5(
                    file_read_for_digest).hexdigest()

                if (final_md5_digest != md5_digest):
                    logger.error("Error en la integridad del archivo. Por "
                                 "favor, descarguelo nuevamente.")
                    os.unlink(filename)

                end_recv_protocol(message_queue, message, socket, address,
                                  stop_event)
                return
            elif message.get_type() == MessageType.ERROR:
                logger.error(f"Error en la descarga -- {message.getErrorCode}")
                send_ack(message.get_seq_number(), socket, address)
                return
