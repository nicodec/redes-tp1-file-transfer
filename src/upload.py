import argparse
from datetime import datetime, timedelta
import logging
import os
import queue
import socket
from threading import Event, Thread
from client.udp_stop_and_wait import upload_saw_client
from message.message import Message, MessageType
from message.utils import recv_message
from utils.misc import CustomHelpFormatter
from utils.logger import logger

DEFAULT_PROTOCOL = 'udp_saw'

def upload_help():
    print("Usage : upload [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [ - s FILEPATH ] [ - n FILENAME ]")
    print("optional arguments:")
    print("-h , --help show this help message and exit")
    print("-v , --verbose increase output verbosity")
    print("-q , --quiet decrease output verbosity")
    print("-H , --host server IP address")
    print("-p , --port server port")
    print("-s , --src source file path")
    print("-n , --name file name")


def parse_arguments():
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description="UPLOAD Description", formatter_class=CustomHelpFormatter)
    
    # Verbosity options
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity_group.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    
    # Required parameters
    parser.add_argument("-H", "--host", metavar="ADDR", type=str, required=True, help="server IP address")
    parser.add_argument("-p", "--port", metavar="PORT", type=int, required=True, help="server port")
    parser.add_argument("-s", "--src", metavar="FILEPATH", type=str, required=True, help="source file path")
    parser.add_argument("-n", "--name", metavar="FILENAME", type=str, required=True, help="file name")
    
    parser.add_argument("-r", "--protocol", metavar="protocol", type=str, help="error recovery protocol", 
                        default="udp_basic", choices=["udp_basic", "udp_saw", "udp_sr"])
    
    parser.usage = parser.format_usage()
    for a in parser._actions:
        a.metavar = '\b'
    
    return parser.parse_args()


def start():
    """Inicia el cliente para subir un archivo"""
    args = parse_arguments()

    # Configuración del nivel de logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.INFO)
    
    if not args.host or not args.port or not args.src or not args.name:
        upload_help()
        return -1
    
    # Configuración de parámetros
    host = args.host
    port = args.port
    path = args.src
    upload_file_name = args.name
    protocol = args.protocol

    # Validar el archivo fuente
    if not os.path.exists(path):
        logger.error(f"El archivo fuente no existe: {path}")
        return -1
    
    filename = os.path.join(path, upload_file_name)
    file = open(filename, "rb")

    logger.info(f"Conectando al servidor {host}:{port}")
    logger.info(f"Protocolo seleccionado: {protocol}")
    logger.info(f"Archivo fuente: {filename}")

    # Crear socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (host, port)

    # Crear cola de mensajes
    message_queue = queue.Queue()

    # Enviar mensaje de subida
    upload_message = Message.upload(os.path.getsize(filename), upload_file_name)
    start_time = datetime.now()
    print(f"Enviando mensaje de subida al servidor: {upload_message}")
    print(f"PATH : {path}")
    print(f"FILENAME : {filename}")
    logger.info(f"Empiezo proceso de subida para el archivo: {path}")
    stop_event = Event()

    # Seleccionar protocolo de envío
    #send_protocol = upload_sr_cliente if protocol == "udp_sr" else upload_saw_cliente
    
    # Por ahora hardcodeo a stop and wait
    send_protocol = upload_saw_client
    send_worker = Thread(target=send_protocol, args=(upload_message, sock, server_address, message_queue, file, stop_event))
    send_worker.start()

    # Manejo de timeout
    timeout = datetime.now() + timedelta(seconds=15)
    timeout_exit = True
    while datetime.now() < timeout:
        try:
            message, _ = recv_message(sock)
            if not send_worker.is_alive():
                timeout_exit = False
                break
            if message:
                if message.get_type() in [MessageType.ACK, MessageType.ERROR, MessageType.END, MessageType.DATA]:
                    message_queue.put(message)
                    timeout = datetime.now() + timedelta(seconds=15)
                else:
                    logger.error("Mensaje no reconocido.")
                    return -1
        except KeyboardInterrupt:
            stop_event.set()
            logger.info("Se ha interrumpido la transferencia.")
            if file:
                file.close()
            sock.close()
            return -1

    if timeout_exit:
        stop_event.set()
        logger.error("No se ha recibido respuesta del servidor.")
    else:
        logger.info(f"Tiempo de transferencia: {datetime.now() - start_time}")
    if file:
        file.close()
    sock.close()
    return 0


if __name__ == "__main__":
    start()
