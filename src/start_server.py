
import socket
import os
import logging
import argparse
from threading import Thread, Event
import queue
from server.server_client import Client
from message.message import TOTAL_BYTES_LENGTH, ErrorCode, Message, MessageType
from server.udp_stop_and_wait.upload import upload_saw_server
from server.udp_stop_and_wait.download import download_saw_server
from utils.misc import CustomHelpFormatter
from utils.logger import logger

DEFAULT_PROTOCOL = 'udp_saw'
MAX_FILE_SIZE = 1024 * 1024 * 100  # 100 MB


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
        print("UDP SR protocol not implemented yet.")
        # protocol_handler = upload_sr_server

    if protocol_handler:
        worker_thread = Thread(target=protocol_handler,
                               args=(initial_message, sock, client_address,
                                     messages_queue, file, filename,
                                     stop_event))
        worker_thread.start()
        join_worker(worker_thread, client_address, stop_event, file)


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
        # recv_protocol = download_sr_server
        print("UDP SR protocol not implemented yet.")

    send_worker = Thread(target=recv_protocol,
                         args=(first_message, sock, client_address,
                               messages_queue, file, stop_event, ))
    send_worker.start()
    join_worker(send_worker, client_address, stop_event, file)


def parse_arguments():
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description="START SERVER Description", formatter_class=CustomHelpFormatter)
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity_group.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    parser.add_argument("-H", "--host", metavar="ADDR", type=str, help="service IP address", default="localhost")
    parser.add_argument("-p", "--port", type=int, help="service port", default=8888)
    parser.add_argument("-s", "--storage", metavar="DIRPATH", type=str, help="storage dir path", 
                        default=os.getcwd() + '/server/files')
    parser.add_argument("-r", "--protocol", metavar="protocol", type=str, help="error recovery protocol",
                        default=DEFAULT_PROTOCOL, choices=["udp_saw", "udp_sr"])

    parser.usage = parser.format_usage()
    for a in parser._actions:
        a.metavar = '\b'

    return parser.parse_args()


def start_server():
    """Inicia el servidor UDP"""
    args = parse_arguments()

    path = os.getcwd() + '/server/files'

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.INFO)

    path = args.storage
    # Crear directorio de almacenamiento si no existe
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"Directorio de almacenamiento creado: {path}")

    protocol = args.protocol if args.protocol else DEFAULT_PROTOCOL

    # Crear socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (args.host, args.port)
    sock.bind(server_address)

    logger.info(f"Servidor iniciado en: {server_address}")
    logger.info(f"Almacenamiento: {path}")
    logger.info(f"Protocolo: {args.protocol}")

    # Diccionario para mantener los clientes conectados
    clients = {}

    try:
        logger.info("Esperando mensajes...")
        while True:
            # Recibir mensaje
            message, client_address = recv_message(sock)

            if message:
                # Crear o actualizar cliente
                if (message.get_type() == MessageType.UPLOAD or message.get_type() == MessageType.DOWNLOAD) and client_address in clients:
                    clients[client_address].add_message(message)
                    continue

                # logger.info(f"Mensaje recibido desde {client_address}: {message}")

                # Procesar el mensaje según su tipo
                if message.get_type() == MessageType.UPLOAD:
                    logger.info(f"Cliente {client_address} se ha conectado.")
                    logger.info(f"Solicitud de subida de archivo: {message.get_file_name()}")
                    messages_queue = queue.Queue()
                    filename = os.path.join(path, message.get_file_name())
                    stop_event = Event()
                    upload_worker = Thread(target=upload,
                                           args=(sock, client_address, message,
                                                 messages_queue, filename, 
                                                 stop_event, protocol))
                    clients[client_address] = Client(client_address, upload_worker, messages_queue, stop_event)
                    clients[client_address].run()

                elif message.get_type() == MessageType.DOWNLOAD:
                    logger.info(f"Cliente {client_address} se ha conectado.")
                    logger.info(f"Archivo a descargar: {message.get_file_name()}")
                    messages_queue = queue.Queue()
                    filename = os.path.join(path, message.get_file_name())
                    stop_event = Event()
                    download_worker = Thread(target=download, args=(sock, client_address, messages_queue, filename, stop_event, protocol))
                    clients[client_address] = Client(client_address, download_worker, messages_queue, stop_event)
                    clients[client_address].run()

                elif message.get_type() == MessageType.ERROR or message.get_type() == MessageType.ACK or message.get_type() == MessageType.DATA or message.get_type() == MessageType.END or message.get_type() == MessageType.ACK_END:
                    if (client_address in clients):
                        clients[client_address].add_message(message)
                else:
                    logger.error("Mensaje no reconocido.")

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
        sock.close()
        logger.info("Servidor detenido.")


if __name__ == "__main__":
    start_server()