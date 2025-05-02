from message.message import DATA_MAX_SIZE, Message, MessageType
from message.utils import send_message, get_message_from_queue
from utils.logger import logger


def finalizar_servidor(sock, client_address, msg_queue, stop_event):
    """Finaliza la conexión con el cliente enviando un ACK al recibir
    un mensaje END."""
    ack_message = Message.ack(0)
    message = get_message_from_queue(msg_queue)

    send_message(ack_message, sock, client_address)

    recibi_nuevamente_fin = not message or message.get_type() == MessageType.END
    while recibi_nuevamente_fin:
        if stop_event.is_set():
            return
        if ack_message.is_timeout():
            send_message(ack_message, sock, client_address)
        response = get_message_from_queue(msg_queue)
        recibi_nuevamente_fin = not response or response.get_type() == MessageType.END
