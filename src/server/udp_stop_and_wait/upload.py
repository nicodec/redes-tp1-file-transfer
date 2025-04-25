from datetime import datetime, timedelta
import os
from server.udp_stop_and_wait.finalizar_servidor import finalizar_servidor
from message.message import Message, MessageType
from message.utils import (
    send_ack, send_message, get_message_from_queue, show_info
)
from utils.logger import logger


def inicio_upload_server(sock, client_address, mensaje_inicial, msg_queue, stop_event):
    """Inicia el protocolo de subida verificando errores y esperando el ACK inicial."""
    logger.info("Iniciando protocolo de subida.")
    
    # Manejo del caso de error: archivo demasiado grande o problema inicial
    if mensaje_inicial.get_type() == MessageType.ERROR:
        logger.error("Error detectado en el mensaje inicial.")
        error_procesado = False
        while not error_procesado:
            if stop_event.is_set():
                logger.error("El proceso de subida fue interrumpido.")
                return None
            if mensaje_inicial.is_timeout():
                logger.debug("Reenviando mensaje de error al cliente.")
                send_message(mensaje_inicial, sock, client_address)
            respuesta = get_message_from_queue(msg_queue)
            if respuesta and respuesta.get_type() == MessageType.END:
                logger.info("Cliente finalizó el proceso de subida debido a un error.")
                finalizar_servidor(sock, client_address, msg_queue, stop_event)
                error_procesado = True
        return True

    # Esperar el ACK inicial del cliente
    ack_recibido = False
    mensaje_ack = Message.ack(0)
    while not ack_recibido:
        if stop_event.is_set():
            logger.error("El proceso de subida fue interrumpido antes de recibir el ACK inicial.")
            return None
        if mensaje_ack.is_timeout():
            logger.debug(f"Enviando ACK inicial al cliente {client_address}.")
            send_message(mensaje_ack, sock, client_address)
        respuesta = get_message_from_queue(msg_queue)
        if respuesta and respuesta.get_type() == MessageType.ACK:
            ack_recibido = True
            logger.info("ACK inicial recibido del cliente.")
        elif respuesta and respuesta.get_type() == MessageType.DATA and respuesta.get_seq_number() == 1:
            ack_recibido = True
            logger.info("Primer paquete recibido, lo que indica que el cliente recibió el ACK inicial.")

    logger.info("Inicio del protocolo de subida completado.")
    return False


def upload_saw_server(mensaje_inicial, sock, client_address, msg_queue, file, filename, stop_event):
    """Protocolo Stop-and-Wait para la subida de archivos al servidor."""
    inicio = datetime.now()
    error_detectado = inicio_upload_server(sock, client_address, mensaje_inicial, msg_queue, stop_event)

    if error_detectado:
        if file:
            file.close()
            os.remove(filename)
        return

    logger.info("Preparando el servidor para recibir el archivo.")

    bytes_recibidos = 0
    secuencia_actual = 1
    proxima_actualizacion = inicio + timedelta(seconds=1)
    
    buffer_datos = []

    while bytes_recibidos < mensaje_inicial.get_file_size():
        proxima_actualizacion = show_info(mensaje_inicial.get_file_size(), bytes_recibidos, inicio, proxima_actualizacion)

        if stop_event.is_set():
            if file:
                file.close()
                os.remove(filename)
            return

        paquete_recibido = False
        while not paquete_recibido:
            if stop_event.is_set():
                if file:
                    file.close()
                    os.remove(filename)
                return

            mensaje = get_message_from_queue(msg_queue)

            # Caso de retransmisión de ACK para un paquete anterior
            if mensaje:
                if mensaje.get_type() == MessageType.DATA and mensaje.get_seq_number() < secuencia_actual:
                    logger.debug(f"Retransmitiendo ACK para el paquete {mensaje.get_seq_number()}.")
                    send_ack(mensaje.get_seq_number(), sock, client_address)

                # Caso de recepción del paquete esperado
                elif mensaje.get_type() == MessageType.DATA and mensaje.get_seq_number() == secuencia_actual:
                    logger.debug(f"Paquete {mensaje.get_seq_number()} recibido correctamente.")
                    datos = mensaje.get_data()
                    buffer_datos.append(datos)

                    # Escribir en el archivo si el buffer
                    # alcanza un tamaño considerable
                    if sum(len(chunk) for chunk in buffer_datos) > 50000:
                        file.write(b"".join(buffer_datos))
                        buffer_datos.clear()

                    bytes_recibidos += len(datos)
                    logger.debug(f"Enviando ACK para el paquete {mensaje.get_seq_number()}.")
                    send_ack(mensaje.get_seq_number(), sock, client_address)
                    secuencia_actual += 1
                    paquete_recibido = True

    # Escribir cualquier dato restante en el buffer
    if buffer_datos:
        file.write(b"".join(buffer_datos))

    logger.info("Archivo recibido exitosamente.")
    logger.info("Iniciando proceso de finalización de la subida.")
    finalizar_servidor(sock, client_address, msg_queue, stop_event)
    logger.info("Proceso de subida finalizado.")

    if file:
        file.close()
