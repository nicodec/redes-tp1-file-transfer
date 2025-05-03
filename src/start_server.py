import socket
import os
import logging
import argparse
from threading import Thread, Event
import queue
from typing import Any
from server.server_client import Client
from message.message import TOTAL_BYTES_LENGTH, ErrorCode, Message, MessageType
from server.udp_stop_and_wait.upload import upload_saw_server
from server.udp_stop_and_wait.download import download_saw_server
from server.udp_selective_repeat.upload import upload_sr_server
from server.udp_selective_repeat.download import download_sr_server
from utils.misc import CustomHelpFormatter
from utils.logger import logger

DEFAULT_PROTOCOL = 'udp_saw'
MAX_FILE_SIZE = 1024 * 1024 * 100  # 100 MB


class ServerData:
    """Estructura que contiene el estado del server"""
    def __init__(self):
        self.sock = None
        self.storage_path = ""
        self.clients = dict[Any, Client]()
        self.protocol = DEFAULT_PROTOCOL


def recv_message(sock, timeout=None):
    sock.settimeout(timeout)
    try:
        raw_message, address = sock.recvfrom(TOTAL_BYTES_LENGTH)
        message = Message.from_bytes(raw_message)
        return message, address
    except TimeoutError:
        return None, None


def join_worker(worker, client_address, stop_event, file, timeout=1800):
    worker.join(timeout)  # Timeout de 30 minutos
    if worker.is_alive():
        logger.error(f"EL cliente {client_address} ha tardado más de "
                     f"30 minutos en responder, desconectando...")
        stop_event.set()
    if file:
        file.close()


def upload(sock, client_address,
           message, messages_queue,
           filename, stop_event, protocol):
    file = None
    initial_message = message

    if os.path.exists(filename):
        logger.error(f"El archivo {filename} ya existe en el servidor.")
        initial_message = Message.error(ErrorCode.FILE_ALREADY_EXISTS)
    elif message.get_file_size() > MAX_FILE_SIZE:
        logger.error(f"El tamaño del archivo {filename} excede el "
                     f"límite permitido.")
        initial_message = Message.error(ErrorCode.FILE_TOO_BIG)
    else:
        try:
            file = open(filename, "ab")
        except IOError as e:
            logger.error(f"No se pudo abrir el archivo {filename} para "
                         f"escritura: {e}")
            initial_message = Message.error(ErrorCode.FILE_WRITE_ERROR)

    protocol_handler = None
    if protocol == 'udp_saw':
        protocol_handler = upload_saw_server
    elif protocol == 'udp_sr':
        protocol_handler = upload_sr_server

    if protocol_handler:
        worker_thread = Thread(target=protocol_handler,
                               args=(initial_message, sock, client_address,
                                     messages_queue, file, filename,
                                     stop_event))
        worker_thread.start()
        join_worker(worker_thread, client_address, stop_event, file)
    
    logger.info(f"El cliente {client_address} ha terminado la subida ")


def download(sock, client_address, messages_queue,
             filename, stop_event, protocol):
    first_message = None
    file = None

    if not os.path.exists(filename):
        logger.error(f"El archivo {filename} no se ha encontrado.")
        first_message = Message.error(ErrorCode.FILE_NOT_FOUND)
    else:
        file = open(filename, "rb")
        file_size = os.path.getsize(filename)
        first_message = Message.ack_download(file_size)
    recv_protocol = None
    if protocol == 'udp_saw':
        recv_protocol = download_saw_server
    elif protocol == 'udp_sr':
        recv_protocol = download_sr_server

    send_worker = Thread(target=recv_protocol,
                         args=(first_message, sock, client_address,
                               messages_queue, file, stop_event))
    send_worker.start()
    join_worker(send_worker, client_address, stop_event, file)


def parse_arguments():
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description="START SERVER Description",
                                     formatter_class=CustomHelpFormatter)
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_true",
                                 help="increase output verbosity")
    verbosity_group.add_argument("-q", "--quiet", action="store_true",
                                 help="decrease output verbosity")
    parser.add_argument("-H", "--host", metavar="ADDR", type=str,
                        help="service IP address", default="localhost")
    parser.add_argument("-p", "--port", type=int,
                        help="service port", default=8888)
    parser.add_argument("-s", "--storage", metavar="DIRPATH", type=str,
                        help="storage dir path",
                        default=os.getcwd() + '/server/files')
    parser.add_argument("-r", "--protocol", metavar="protocol", type=str,
                        help="error recovery protocol",
                        default=DEFAULT_PROTOCOL,
                        choices=["udp_saw", "udp_sr"])

    parser.usage = parser.format_usage()
    for a in parser._actions:
        a.metavar = '\b'

    return parser.parse_args()


def process_client_message(server_data: ServerData, message: Message,
                           client_address):
    """Dado un mensaje proveniente del cliente ya deserializado, segun su tipo:
    UPLOAD: Inicia un flujo de subida con el cliente
    DOWNLOAD: Inicia un flujo de descarga con el cliente
    ERROR, ACK, DATA, END, ACK_END: Deriva el mensaje al flujo con el cliente
    """
    # Crear o actualizar cliente
    msg_type = message.get_type()
    if (msg_type in [MessageType.UPLOAD, MessageType.DOWNLOAD] and
            client_address in server_data.clients):
        server_data.clients[client_address].add_message(message)
        return

    # logger.info(f"Mensaje recibido desde {client_address}: {message}")

    # Procesar el mensaje según su tipo
    if msg_type == MessageType.UPLOAD:
        msg_file_name = message.get_file_name()
        logger.info(f"Cliente {client_address} se ha conectado.")
        logger.info(f"Solicitud de subida de archivo: {msg_file_name}")
        messages_queue = queue.Queue()
        filename = os.path.join(server_data.storage_path, msg_file_name)
        stop_event = Event()
        upload_worker = Thread(
            target=upload, args=(server_data.sock, client_address, message,
                                 messages_queue, filename, stop_event,
                                 server_data.protocol))
        server_data.clients[client_address] = Client(
            client_address, upload_worker, messages_queue, stop_event)
        server_data.clients[client_address].run()

    elif msg_type == MessageType.DOWNLOAD:
        msg_file_name = message.get_file_name()
        logger.info("\033[32m+-----------------------------------------------+")
        logger.info(f"\033[32m| Cliente {client_address} se ha conectado. |")
        logger.info("\033[32m+-----------------------------------------------+")
        logger.info(f"Archivo a descargar: {msg_file_name}")
        messages_queue = queue.Queue()
        filename = os.path.join(server_data.storage_path, msg_file_name)
        stop_event = Event()
        download_worker = Thread(
            target=download, args=(server_data.sock, client_address,
                                   messages_queue, filename, stop_event,
                                   server_data.protocol))
        server_data.clients[client_address] = Client(
            client_address, download_worker, messages_queue, stop_event)
        server_data.clients[client_address].run()

    elif msg_type in [MessageType.ERROR, MessageType.ACK, MessageType.DATA,
                      MessageType.END, MessageType.ACK_END]:
        if (client_address in server_data.clients):
            server_data.clients[client_address].add_message(message)
    else:
        logger.error("Mensaje no reconocido.")


def start_server():
    """Inicia el servidor UDP"""
    args = parse_arguments()
    server_data = ServerData()

    server_data.storage_path = os.getcwd() + '/server/files'

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.INFO)

    if args.protocol is not None:
        server_data.protocol = args.protocol

    if args.storage is not None:
        server_data.storage_path = args.storage

    # Crear directorio de almacenamiento si no existe
    if not os.path.exists(server_data.storage_path):
        os.makedirs(server_data.storage_path)
        logger.info(f"Directorio de almacenamiento creado: \
                    {server_data.storage_path}")

    # Crear socket UDP
    server_data.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (args.host, args.port)
    server_data.sock.bind(server_address)

    logger.info("\033[32m+-------------------------------------+")
    logger.info(f"\033[32m| Servidor iniciado en {args.host}:{args.port} |")
    logger.info("\033[32m+-------------------------------------+")
    logger.info(f"Protocolo: {args.protocol}")

    # Diccionario para mantener los clientes conectados
    clients = dict[Any, Client]()

    try:
        logger.info("Esperando mensajes...")
        while True:
            # Recibir mensaje
            message, client_address = recv_message(server_data.sock)

            if message:
                process_client_message(server_data, message, client_address)

            # Verificar clientes inactivos
            clients_to_remove = []
            for addr, client in clients.items():
                if client.is_timeout():
                    logger.info(f"Cliente {addr} desconectado por timeout")
                    clients_to_remove.append(addr)

            # Eliminar clientes inactivos
            for addr in clients_to_remove:
                del clients[addr]

    except KeyboardInterrupt:
        logger.info("Deteniendo servidor...")
        logger.info(f"Desconectando {len(clients)} clientes activos")
        server_data.sock.close()
        logger.info("Servidor detenido.")


if __name__ == "__main__":
    start_server()
