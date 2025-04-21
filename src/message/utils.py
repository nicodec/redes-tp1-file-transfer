from datetime import datetime, timedelta
import logging
from random import randint
from message.message import TOTAL_BYTES_LENGTH, Message

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cliente_udp')

def send_ack(secNumber, socket, address):
    ack_message = Message.ack(secNumber)
    send_message(ack_message, socket, address)

def recv_message(socket, timeout = 1):
    socket.settimeout(timeout)
    try:
        raw_message, address = socket.recvfrom(TOTAL_BYTES_LENGTH)
        message = Message.from_bytes(raw_message)
        return message, address
    except TimeoutError:
        return None, None
    
def send_message(message, socket, address):
    message.set_timeout(1)
    if not lost_message():
        bytes_to_send = message.to_bytes()
        socket.sendto(bytes_to_send, address)


def lost_message():
    random_number = randint(0, 100)
    return random_number < 0

def send_ack(secNumber, socket, address):
    ack_message = Message.ack(secNumber)
    send_message(ack_message, socket, address)

def get_message_from_queue(message_queue):
    return message_queue.get(False) if not message_queue.empty() else None

def show_info(total, parcial, start_time, next_update):
    if datetime.now() > next_update:
        logger.info(f"Total: {total} bytes, Partial: {parcial} bytes, Time: {datetime.now() - start_time}")
        return datetime.now() + timedelta(seconds=1)
    return next_update
