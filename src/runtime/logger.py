import logging

from colorama import Fore, Style, init


init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.WHITE,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }
    NAME_COLOR = Fore.MAGENTA
    MESSAGE_COLOR = Fore.WHITE
    TIME_COLOR = Fore.GREEN

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        levelname = level_color + record.levelname + Style.RESET_ALL
        name = self.NAME_COLOR + record.name + Style.RESET_ALL
        message = self.MESSAGE_COLOR + record.getMessage() + Style.RESET_ALL
        asctime = self.TIME_COLOR + self.formatTime(record, self.datefmt) + Style.RESET_ALL
        return f"{asctime} [{levelname}] {name} | {message}"


def register_logger(name: str, level: str = "DEBUG") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
