
import socket
import sys
import os
import logging
import argparse
from threading import Thread, Event
import queue
import time
from datetime import datetime, timedelta
from server.server_client import Client
from message.message import TOTAL_BYTES_LENGTH, ErrorCode, Message, MessageType
from utils.misc import CustomHelpFormatter

# Configuración del logger
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('servidor_udp')

DEFAULT_PROTOCOL = 'udp_saw'

def recv_message(sock, timeout=None):
    socket.settimeout(timeout)
    try:
        raw_message, address = socket.recvfrom(TOTAL_BYTES_LENGTH)
        message = Message.fromBytes(raw_message)
        return message, address
    except TimeoutError:
        return None, None

def upload(sock, client_address, message, messages_queue, filename, stop_event, protocol):
    pass

def download(sock, client_address, messages_queue, filename, stop_event, protocol):
    pass

def parse_arguments():
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description="START SERVER Description", formatter_class=CustomHelpFormatter)
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity_group.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    parser.add_argument("-H", "--host", metavar="ADDR", type=str, help="service IP address", default="localhost")
    parser.add_argument("-p", "--port", type=int, help="service port", default=3333)
    parser.add_argument("-s", "--storage", metavar="DIRPATH", type=str, help="storage dir path", 
                        default=os.getcwd() + '/server/files')
    parser.add_argument("-r", "--protocol", metavar="protocol", type=str, help="error recovery protocol",
                        default="udp_basic", choices=["udp_basic", "udp_saw", "udp_sr"])

    parser.usage = parser.format_usage()
    for a in parser._actions:
        a.metavar='\b'
    
    return parser.parse_args()

def start_server():
    """Inicia el servidor UDP"""
    args = parse_arguments()

    #Namespace(host='127.0.0.1', port=8080, protocol='udp_saw', quiet=False, storage='/tmp/storage', verbose=True)
    path = os.getcwd() + '/server/files'

    # Configuración del nivel de logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.INFO)
    
    # Crear directorio de almacenamiento si no existe
    if not os.path.exists(args.storage):
        os.makedirs(args.storage)
        logger.info(f"Directorio de almacenamiento creado: {args.storage}")

    protocol = DEFAULT_PROTOCOL

    protocol = args.protocol

    # if args['udp_saw']:
    #     protocol = 'udp_saw'

    # if args['udp_sr']:
    #     protocol = 'udp_sr'
    
    # Crear socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Enlazar socket
    server_address = (args.host, args.port)
    sock.bind(server_address)
    
    logger.info(f"Servidor iniciado en: {server_address}")
    logger.info(f"Almacenamiento: {args.storage}")
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
                    clients[client_address].add_message()
                    continue
                
                logger.info(f"Mensaje recibido desde {client_address}: {message}")
                
                # Procesar el mensaje según su tipo
                if message.get_type() == MessageType.UPLOAD:
                    logger.info(f"Solicitud de subida de archivo: {message.get_file_name()}")
                    messages_queue = queue.Queue()
                    filename = path + "/" + message.get_file_name()
                    stop_event = Event()
                    upload_worker = Thread(target=upload, args=(sock, client_address, message, messages_queue, filename, stop_event, protocol ))
                    clients[client_address] = Client(client_address, upload_worker, messages_queue, stop_event)
                    clients[client_address].run()
                
                elif message.get_type() == MessageType.DOWNLOAD:
                    logger.info(f"Cliente {client_address} se ha conectado.")
                    logger.info(f"Archivo a descargar: {message.get_file_name()}")
                    messages_queue = queue.Queue()
                    filename = path + "/" + message.get_file_name()
                    stop_event = Event()
                    download_worker = Thread(target=download, args=(sock, client_address, messages_queue, filename, stop_event, protocol))
                    clients[client_address] = Client(client_address, download_worker, messages_queue, stop_event)
                    clients[client_address].run()
                
                elif message.getType() == MessageType.ERROR or message.getType() == MessageType.ACK or message.getType() == MessageType.DATA or message.getType() == MessageType.END or message.getType() == MessageType.ACK_END:
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