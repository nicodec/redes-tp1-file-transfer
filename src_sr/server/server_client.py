import time
from utils.logger import logger


class Client:
    """Clase para manejar la conexión con un cliente"""
    def __init__(self, address,
                 worker, messages_queue,
                 stop_event, timeout=30):
        """
        Inicializa un cliente
        Args:
            address: Tupla (host, port) del cliente
            worker: Thread que procesa los mensajes del cliente
            messages_queue: Cola para los mensajes recibidos
            stop_event: Evento para detener el worker
            timeout: Tiempo máximo de inactividad antes de desconectar
        """
        self.address = address
        self.worker = worker
        self.messages_queue = messages_queue
        self.stop_event = stop_event
        self.last_activity = time.time()
        self.timeout = timeout

    def run(self):
        """Inicia el worker del cliente"""
        self.worker.start()

    def add_message(self, message):
        """Añade un mensaje a la cola"""
        self.messages_queue.put(message)
        self.last_activity = time.time()

    def is_alive(self):
        """Comprueba si el worker sigue vivo"""
        return self.worker.is_alive()

    def is_timeout(self):
        """Comprueba si el cliente ha superado el tiempo de inactividad"""
        return time.time() - self.last_activity > self.timeout

    def timeout_disconect(self):
        """Desconecta al cliente por timeout"""
        logger.info(f"Cliente {self.address} desconectado por timeout.")
        self.stop_event.set()
        if self.worker.is_alive():
            self.worker.join(2)  # Esperar 2 segundos a que termine

    def disconnect(self):
        """Desconecta al cliente"""
        logger.info(f"Desconectando cliente {self.address}...")
        self.stop_event.set()
        if self.worker.is_alive():
            self.worker.join(2)  # Esperar 2 segundos a que termine
