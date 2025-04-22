from datetime import datetime, timedelta
from message.message import DATA_MAX_SIZE, Message, MessageType
from message.utils import (
    send_message, send_ack, get_message_from_queue, show_info
)
import os
from utils.logger import logger

DATA_MAX_SIZE = DATA_MAX_SIZE


def finalizar_servidor(sock, client_address, msg_queue, stop_event):
    """Finaliza la conexión con el cliente enviando un ACK al recibir
    un mensaje END."""
    logger.info("Iniciando proceso de finalización con el cliente.")
    ack_message = Message.ack(0)
    message = get_message_from_queue(msg_queue)

    send_message(ack_message, sock, client_address)

    recibi_nuevamente_fin = not message or message.get_type() == MessageType.END
    while recibi_nuevamente_fin:
        if stop_event.is_set():
            return
        if ack_message.is_timeout():
            send_message(ack_message, sock, client_address)
        response = get_message_from_queue(msg_queue)
        recibi_nuevamente_fin = not response or response.get_type() == MessageType.END


########################
## CASO PARA DOWNLOAD ##
########################
def inicio_download_server(sock, client_address, first_message, msg_queue, stop_event):
    """Inicia el proceso de descarga verificando errores y enviando el tamaño del archivo."""
    logger.info("Iniciando protocolo de descarga.")
    error_detectado = False

    # Caso de error: archivo no encontrado
    if first_message.get_type() == MessageType.ERROR:
        error_detectado = True
        logger.error("El archivo solicitado no existe.")
        while not stop_event.is_set():
            if first_message.is_timeout():
                send_message(first_message, sock, client_address)
            response = get_message_from_queue(msg_queue)
            if response and response.get_type() == MessageType.END:
                logger.info("Cliente finalizó el proceso de descarga.")
                finalizar_servidor(sock, client_address, msg_queue, stop_event)
                break

    return error_detectado


def download_saw_server(first_message, sock,
                        client_address, msg_queue,
                        file, stop_event):
    """Implementa el protocolo Stop-and-Wait para la descarga de archivos."""
    start_time = datetime.now()
    error_detectado = inicio_download_server(sock, client_address, first_message, msg_queue, stop_event)

    if error_detectado:
        return

    logger.info(f"Tamaño del archivo: {first_message.get_file_size()} bytes.")
    ack_recibido = False

    # Esperar el ACK inicial del cliente
    while not ack_recibido:
        if stop_event.is_set():
            return
        if first_message.is_timeout():
            logger.debug(f"Reenviando ACK inicial al cliente {client_address}.")
            send_message(first_message, sock, client_address)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.ACK:
            ack_recibido = True
            logger.info("ACK inicial recibido. Preparando envío del archivo.")

    # Enviar el archivo en paquetes
    next_update = start_time + timedelta(seconds=1)
    paquete_actual = 1
    while data := file.read(DATA_MAX_SIZE):
        next_update = show_info(first_message.get_file_size(), paquete_actual * DATA_MAX_SIZE, start_time, next_update)
        ack_recibido = False
        if stop_event.is_set():
            return
        paquete = Message.data(paquete_actual, data)
        while not ack_recibido:
            if stop_event.is_set():
                return
            if paquete.is_timeout():
                logger.debug(f"Reenviando paquete {paquete_actual}.")
                send_message(paquete, sock, client_address)
            response = get_message_from_queue(msg_queue)
            if response and response.get_type() == MessageType.ACK and response.get_seq_number() == paquete_actual:
                logger.debug(f"ACK recibido para el paquete {paquete_actual}.")
                paquete_actual += 1
                ack_recibido = True
                paquete = Message.data(paquete_actual, data)

    logger.info("Archivo enviado con éxito.")

    # Finalizar la transferencia
    fin_enviado = False
    end_message = Message.end()
    while not fin_enviado:
        if stop_event.is_set():
            return
        if end_message.is_timeout():
            logger.debug("Reenviando mensaje de fin al cliente.")
            send_message(end_message, sock, client_address)
        response = get_message_from_queue(msg_queue)
        if response and response.get_type() == MessageType.END:
            logger.info("Fin del cliente recibido.")
            fin_enviado = True
            finalizar_servidor(sock, client_address, msg_queue, stop_event)
            logger.info("Proceso de descarga finalizado.")


######################
## CASO PARA UPLOAD ##
######################
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
