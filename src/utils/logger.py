import logging


class ColorLogFormatter(logging.Formatter):
    # ANSI escape sequences para colores
    COLORS = {
        'DEBUG': "\033[36m",      # Celeste
        'INFO': "\033[32m",       # Verde
        'WARNING': "\033[33m",    # Amarillo
        'ERROR': "\033[31m",      # Rojo
        'CRITICAL': "\033[41m\033[97m",  # Fondo rojo, texto blanco
        'RESET': "\033[0m"
        
    }

    def format(self, record):
        level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        log_format = (
            f"{level_color}[%(levelname)s]{reset} "
            f"%(asctime)s | %(message)s "
        )
        formatter = logging.Formatter(log_format, datefmt='%H:%M:%S')
        return formatter.format(record)


# Configuramos el logger
logger = logging.getLogger("Tp1 Redes")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(ColorLogFormatter())

logger.addHandler(console_handler)
