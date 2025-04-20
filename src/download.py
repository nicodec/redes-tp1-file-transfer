import argparse
from datetime import datetime, timedelta
import queue
import socket
from threading import Event, Thread
from message.message import Message, MessageType
from message.utils import recv_message
from utils.misc import CustomHelpFormatter
import logging
import os

# Configuración del logger
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cliente_udp')

DEFAULT_PROTOCOL = 'udp_saw'

def download_help():
    print("Usage : download [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [ - d FILEPATH ] [ - n FILENAME ]")
    print("optional arguments:")
    print("-h , --help show this help message and exit")
    print("-v , --verbose increase output verbosity")
    print("-q , --quiet decrease output verbosity")
    print("-H , --host server IP address")
    print("-p , --port server port")
    print("-d , --dst destination file path")
    print("-n , --name file name")


def parse_arguments():
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description="DOWNLOAD Description", formatter_class=CustomHelpFormatter)
    
    # Verbosity options
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity_group.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    
    # Required parameters
    parser.add_argument("-H", "--host", metavar="ADDR", type=str, required=True, help="server IP address")
    parser.add_argument("-p", "--port", metavar="PORT", type=int, required=True, help="server port")
    parser.add_argument("-d", "--dst", metavar="FILEPATH", type=str, required=True, help="destination file path")
    parser.add_argument("-n", "--name", metavar="FILENAME", type=str, required=True, help="file name")
    
    parser.add_argument("-r", "--protocol", metavar="protocol", type=str, help="error recovery protocol", 
                        default="udp_basic", choices=["udp_basic", "udp_saw", "udp_sr"])
    
    parser.usage = parser.format_usage()
    for a in parser._actions:
        a.metavar = '\b'
    
    return parser.parse_args()


def start():
    """Inicia el cliente para descargar un archivo"""
    args = parse_arguments()

    # Configuración del nivel de logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.INFO)
    
    if not args.host or not args.port or not args.dst or not args.name:
        download_help()
        return -1
    
    # Validar y preparar el directorio de destino
    if not os.path.exists(args.dst):
        os.makedirs(args.dst)
        logger.info(f"Directorio de destino creado: {args.dst}")
    
    # Configuración de parámetros
    host = args.host
    port = args.port
    protocol = args.protocol
    filename = os.path.join(args.dst, args.name)

    logger.info(f"Conectando al servidor {host}:{port}")
    logger.info(f"Protocolo seleccionado: {protocol}")
    logger.info(f"Archivo de destino: {filename}")

    # Crear socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (host, port)

    # Crear cola de mensajes
    message_queue = queue.Queue()

    # Enviar mensaje de descarga
    download_message = Message.download(args.name)
    start_time = datetime.now()
    logger.info(f"Empiezo proceso de descarga para el archivo: {filename}")
    stop_event = Event()

    # Seleccionar protocolo de recepción
    #recv_protocol = download_sr_cliente if protocol == "udp_sr" else download_saw_cliente
    
    recv_protocol = download_saw_cliente
    recv_worker = Thread(target=recv_protocol, args=(download_message, sock, server_address, message_queue, filename, stop_event))
    recv_worker.start()

    # Manejo de timeout
    timeout = datetime.now() + timedelta(seconds=15)
    timeout_exit = True
    while datetime.now() < timeout:
        try:
            message, _ = recv_message(sock)
            if not recv_worker.is_alive():
                timeout_exit = False
                break
            if message:
                if message.getType() in [MessageType.DATA, MessageType.ACK_DOWNLOAD, MessageType.ERROR, MessageType.END, MessageType.ACK]:
                    message_queue.put(message)
                    timeout = datetime.now() + timedelta(seconds=15)
                else:
                    logger.error("Mensaje no reconocido.")
                    return -1
        except KeyboardInterrupt:
            stop_event.set()
            logger.info("Se ha interrumpido la transferencia.")
            sock.close()
            return -1

    if timeout_exit:
        stop_event.set()
        logger.error("No se ha recibido respuesta del servidor.")
    else:
        logger.info(f"Tiempo de transferencia: {datetime.now() - start_time}")

    sock.close()
    return 0


if __name__ == "__main__":
    start()