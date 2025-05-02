from message.message import DATA_MAX_SIZE, Message, MessageType, ErrorCode
from message.utils import send_ack, send_message, send_message_and_retry, send_message_and_wait
from utils.logger import logger


def read_file(file, chunk_size, offset):
    real_offset = offset * chunk_size
    logger.debug(f"Reading file... offset is: {real_offset}")
    file.seek(real_offset)
    return file.read(chunk_size)


def init_window(message):
    file_size = message.get_file_size()
    package_amount = (file_size // DATA_MAX_SIZE) + 1
    window_base = 0
    logger.debug("package_amount: " + str(package_amount))
    window_top = 1 if package_amount < 2 else package_amount // 4
    return package_amount, window_base, window_top


def send_error_message(message, socket, address, message_queue, stop_event, trigger_retry_message):
    error_response = send_message_and_retry(message, socket, address, message_queue, stop_event, [MessageType.ACK], trigger_retry_message)
    if not error_response:
        return None
    if error_response.get_type() == MessageType.ACK:
        send_message(Message.ack(error_response.get_seq_number()), socket, address)
        return error_response


def has_errors(first_message_recv, initial_message):
    return not first_message_recv or first_message_recv.get_type() == MessageType.ERROR or initial_message.get_type() == MessageType.ERROR


def recv_data_message(message, socket, address, received_messages, received_data, package_to_receive_size, window_base, window_top, received_packages, file):
    seqNumber = message.get_seq_number()
    if not received_messages[seqNumber]:
        received_messages[seqNumber] = True
        received_data[seqNumber] = message.get_data()
        received_packages += 1
        logger.debug(f"Received packages {received_packages}")
        logger.debug(f"Window_base {window_base} and window_top {window_top}")

        #move window
        while received_messages[window_base]:
            file.write(received_data[window_base])
            if (window_base + 1) < package_to_receive_size:
                window_base += 1
                if (window_top) < package_to_receive_size:
                    window_top += 1
            else:
                break
    #send ack
    send_ack(seqNumber, socket, address)
    return window_base, window_top, received_packages


def end_send_protocol(message_queue, socket, address, stop_event):
    end_message = Message.end()
    send_message(end_message, socket, address)
    while True:
        if stop_event.is_set():
            return
        if end_message.is_timeout(): # Volver a enviar end_message.
            send_message(end_message, socket, address)
        message = message_queue.get(False) if not message_queue.empty() else None
        if message and message.get_type() == MessageType.ACK_END:
            send_ack(message.get_seq_number(), socket, address)
            logger.debug("Se ha cerrado la conexion correctamente")
            return


def end_recv_protocol(message_queue, end_message, socket, address, stop_event):
    ack_end_message = Message.ack_end(end_message.get_seq_number())
    send_message(ack_end_message, socket, address)
    while True:
        if stop_event.is_set():
            logger.warning("No se ha podido confirmar el mensaje de fin de conexion.")
            return
        message = message_queue.get(False) if not message_queue.empty() else None
        if message and message.get_type() == MessageType.ACK:
            logger.debug("Se ha cerrado la conexion correctamente")
            return
        elif message and message.get_type() == MessageType.END: # Volver a enviar ack_end_message.
            send_message(ack_end_message, socket, address)


def send_first_ack_message(message, socket, address, message_queue, stop_event):
    ack_response = send_message_and_retry(message, socket, address, message_queue, stop_event, [MessageType.DATA], MessageType.UPLOAD)
    return ack_response


def send_first_download_message(message, socket, address, message_queue, stop_event):
    download_response = send_message_and_wait(message, socket, address, message_queue, stop_event, [MessageType.ACK_DOWNLOAD, MessageType.ERROR])
    if not download_response:
        return None, None
    if download_response.get_type() == MessageType.ACK_DOWNLOAD:
        return send_message_and_wait(Message.ack(download_response.get_seq_number()), socket, address, message_queue, stop_event, [MessageType.DATA]), download_response
    elif download_response.get_type() == MessageType.ERROR:
        if download_response.get_error_code() == ErrorCode.FILE_NOT_FOUND:
            logger.error(f"El archivo no se ha encontrado en el servidor")
        return send_message_and_wait(Message.ack(download_response.get_seq_number()), socket, address, message_queue, stop_event, [MessageType.ACK]), download_response


def send_first_upload_message(message, socket, address, message_queue, stop_event):
    upload_response = send_message_and_wait(message, socket, address, message_queue, stop_event, [MessageType.ACK, MessageType.ERROR])
    if not upload_response:
        return None
    if upload_response.get_type() == MessageType.ACK:
        return upload_response
    elif upload_response.get_type() == MessageType.ERROR:
        if upload_response.get_error_code() == ErrorCode.FILE_ALREADY_EXISTS:
            logger.error(f"El archivo ya existe en el servidor")
        elif upload_response.get_error_code() == ErrorCode.FILE_TOO_BIG:
            logger.error(f"El archivo es muy grande, no se puede cargar")
        send_message_and_wait(Message.ack(upload_response.get_seq_number()), socket, address, message_queue, stop_event, [MessageType.ACK])
        return upload_response


def send_first_ack_download_message(message, socket, address, message_queue, stop_event):
    ack_download_response = send_message_and_retry(message, socket, address, message_queue, stop_event, [MessageType.ACK], MessageType.DOWNLOAD)
    return ack_download_response

