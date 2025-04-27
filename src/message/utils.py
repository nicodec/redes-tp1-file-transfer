from datetime import datetime, timedelta
import logging
from random import randint
from message.message import TOTAL_BYTES_LENGTH, Message
from utils.logger import logger


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


def send_message_and_retry(message, socket, address, message_queue, stop_event, waited_messages, trigger_retry_message):
    send_message(message, socket, address)
    while True:
        if stop_event.is_set():
            return None
        recv_message = message_queue.get(False) if not message_queue.empty() else None
        if recv_message:
            if recv_message.get_type() in waited_messages:
                return recv_message
            elif recv_message.get_type() == trigger_retry_message:
                send_message(message, socket, address)


def send_message_and_wait(message, socket, address, message_queue, stop_event, waited_messages):
    send_message(message, socket, address)
    while True:
        if stop_event.is_set():
            return None
        if message.is_timeout():
            send_message(message, socket, address)
        recv_message = message_queue.get(False) if not message_queue.empty() else None
        if recv_message and recv_message.get_type() in waited_messages:
            return recv_message
