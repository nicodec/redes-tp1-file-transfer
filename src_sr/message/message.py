from enum import Enum
from datetime import datetime, timedelta
from utils.logger import logger

SEQUENCE_NUMBER_BYTES = 4
DATA_MAX_SIZE = 2947
TOTAL_BYTES_LENGTH = 1 + SEQUENCE_NUMBER_BYTES + DATA_MAX_SIZE


class MessageType(Enum):
    UPLOAD = 0
    DOWNLOAD = 1
    DATA = 2
    ACK = 3
    ACK_DOWNLOAD = 4
    ACK_END = 5
    ERROR = 6
    END = 7


class ErrorCode(Enum):
    FILE_NOT_FOUND = 0
    FILE_TOO_BIG = 1
    FILE_ALREADY_EXISTS = 2
    FILE_WRITE_ERROR = 3


class Message:
    def __init__(self, msg_type, seq_number=0, data=None, timeout=0):
        """
        Inicializa un mensaje

        Args:
            msg_type: Tipo de mensaje (MessageType)
            seq_number: Número de secuencia (para DATA/ACK)
            data: Datos del mensaje
            timeout: Tiempo en segundos hasta que el mensaje expira
        """
        self.type = msg_type
        self.seq_number = seq_number
        self.data = data if data is not None else b''

        # Verificar tamaño máximo de datos
        if self.data and len(self.data) > DATA_MAX_SIZE:
            logger.error(
                f"Tamaño máximo de datos es {DATA_MAX_SIZE} bytes, "
                f"recibido: {len(self.data)}"
            )
            raise ValueError(
                f"Tamaño máximo de datos es {DATA_MAX_SIZE} bytes"
            )

        # Tiempo de expiración para el mensaje
        self.timeout_time = datetime.now() + timedelta(seconds=timeout)

    def __repr__(self):
        """Representación textual del mensaje"""
        basic = f"Message(type={self.type.name}, seq_number={self.seq_number}"

        if self.type == MessageType.ERROR:
            basic += f", error_code={self.get_error_code().name}"
        elif self.type == MessageType.UPLOAD:
            file_size, file_name, hash = self.get_data_as_string().split("|")
            basic += f", file_size={file_size}, file_name={file_name}, file_hash={hash}"
            logger.debug(f"hash del archivo: {hash}.")
        elif self.type == MessageType.DOWNLOAD:
            basic += f", file_name={self.get_file_name()}"
        elif self.data:
            if len(self.data) > 20:
                data_preview = self.data[:20]
                basic += f", data={data_preview}..."
            else:
                basic += f", data={self.data}"

        return basic + ")"

    def to_bytes(self):
        """Convierte el mensaje a bytes para enviar por la red"""
        # Crear un bytearray con el tipo de mensaje (1 byte)
        result = bytearray(self.type.value.to_bytes(1, 'big'))

        # Añadir el número de secuencia (4 bytes)
        result.extend(self.seq_number.to_bytes(SEQUENCE_NUMBER_BYTES, 'big'))

        # Añadir los datos
        if self.data:
            result.extend(self.data)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data):
        """Crea un mensaje a partir de bytes recibidos"""
        # El primer byte es el tipo de mensaje
        msg_type = MessageType(data[0])

        # Los siguientes 4 bytes son el número de secuencia
        seq_number = int.from_bytes(data[1:SEQUENCE_NUMBER_BYTES + 1], 'big')

        # El resto son los datos
        if len(data) > SEQUENCE_NUMBER_BYTES + 1:
            msg_data = data[SEQUENCE_NUMBER_BYTES + 1:]
        else:
            msg_data = b''

        return cls(msg_type, seq_number, msg_data)

    # Métodos de acceso simplificados

    def get_type(self):
        """Devuelve el tipo de mensaje"""
        return self.type

    def get_seq_number(self):
        """Devuelve el número de secuencia"""
        return self.seq_number

    def get_data(self):
        """Devuelve los datos del mensaje"""
        return self.data

    def get_data_as_string(self):
        """Devuelve los datos como una cadena UTF-8"""
        if not self.data:
            return ""
        return self.data.decode('utf-8')

    def get_file_name(self):
        """Extrae el nombre del archivo del mensaje"""
        if self.type == MessageType.DOWNLOAD:
            return self.get_data_as_string()
        elif self.type == MessageType.UPLOAD:
            parts = self.get_data_as_string().split("|")
            if len(parts) >= 2:
                return parts[1]
        return None
    
    def get_file_digest(self):
        """Extrae el digest del archivo del mensaje"""        
        if self.type == MessageType.UPLOAD:
            parts = self.get_data_as_string().split("|")
            if len(parts) >= 2:
                return parts[2]
        return None

    def get_file_size(self):
        """Extrae el tamaño del archivo del mensaje"""
        if self.type in [MessageType.UPLOAD, MessageType.ACK_DOWNLOAD]:
            parts = self.get_data_as_string().split("|")
            if parts and parts[0].isdigit():
                return int(parts[0])
        return None

    def get_error_code(self):
        """Extrae el código de error del mensaje"""
        if self.type == MessageType.ERROR and self.data:
            error_value = int.from_bytes(self.data, 'big')
            return ErrorCode(error_value)
        return None

    def is_timeout(self):
        """Comprueba si el mensaje ha expirado"""
        return datetime.now() > self.timeout_time

    def set_timeout(self, timeout):
        """Establece un nuevo tiempo de expiración"""
        self.timeout_time = datetime.now() + timedelta(seconds=timeout)

    # Métodos de fábrica estáticos para crear mensajes específicos

    @staticmethod
    def upload(file_size, file_name, md5_digest):
        """Crea un mensaje de subida de archivo"""
        data = f"{file_size}|{file_name}|{md5_digest}".encode('utf-8')
        return Message(MessageType.UPLOAD, 0, data)

    @staticmethod
    def download(file_name):
        """Crea un mensaje de descarga de archivo"""
        data = file_name.encode('utf-8')
        return Message(MessageType.DOWNLOAD, 0, data)

    @staticmethod
    def data(seq_number, data):
        """Crea un mensaje de datos"""
        return Message(MessageType.DATA, seq_number, data)

    @staticmethod
    def ack(seq_number):
        """Crea un mensaje de confirmación"""
        return Message(MessageType.ACK, seq_number)
    
    @staticmethod
    def ack_end_download_saw(seq_number, md5_digest):
        """Crea un mensaje de confirmación de finalizacion de descarga, y contiene el digest para el cliente"""
        data = md5_digest.encode('utf-8')
        return Message(MessageType.ACK, seq_number, data)

    @staticmethod
    def ack_download(file_size):
        """Crea un mensaje de confirmación de descarga"""
        data = str(file_size).encode('utf-8')
        return Message(MessageType.ACK_DOWNLOAD, 0, data)

    @staticmethod
    def ack_end(seq_number=0):
        """Crea un mensaje de confirmación de finalización"""
        return Message(MessageType.ACK_END, seq_number)

    @staticmethod
    def error(error_code):
        """Crea un mensaje de error"""
        data = error_code.value.to_bytes(1, 'big')
        return Message(MessageType.ERROR, 0, data)

    @staticmethod
    def end():
        """Crea un mensaje de finalización"""
        return Message(MessageType.END, 0)

    @staticmethod
    def end_download(md5_digest):
        """Crea un mensaje de finalización de download con el digest correspondiente"""
        data = md5_digest.encode('utf-8')
        return Message(MessageType.END, 0, data)