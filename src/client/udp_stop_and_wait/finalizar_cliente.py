from message.message import Message, MessageType
from message.utils import send_message, send_ack, get_message_from_queue
from utils.logger import logger

def finalizar_cliente(sock, server_addr, msg_queue, stop_event):
    """
    Finaliza la conexión con el servidor enviando un mensaje de fin y esperando un ACK.
    """
    end_msg = Message.end()
    while not stop_event.is_set():
        if end_msg.is_timeout():
            send_message(end_msg, sock, server_addr)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.ACK:
            send_ack(response.get_seq_number(), sock, server_addr)
            break
