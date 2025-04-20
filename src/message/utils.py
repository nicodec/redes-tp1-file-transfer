from message.message import TOTAL_BYTES_LENGTH, Message


def recv_message(socket, timeout = 1):
    socket.settimeout(timeout)
    try:
        raw_message, address = socket.recvfrom(TOTAL_BYTES_LENGTH)
        message = Message.fromBytes(raw_message)
        return message, address
    except TimeoutError:
        return None, None