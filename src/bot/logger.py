import logging
from colorama import Fore, Style, init

# 初始化 colorama
init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.WHITE,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }
    NAME_COLOR = Fore.MAGENTA  # logger 名称的颜色
    MESSAGE_COLOR = Fore.WHITE  # 消息的颜色
    TIME_COLOR = Fore.GREEN  # 时间戳的颜色

    def format(self, record):
        level_color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        levelname = level_color + record.levelname + Style.RESET_ALL
        # 设置 logger 名称颜色
        name = self.NAME_COLOR + record.name + Style.RESET_ALL
        # 设置消息颜色
        message = self.MESSAGE_COLOR + record.getMessage() + Style.RESET_ALL
        # 设置时间戳颜色
        asctime = self.TIME_COLOR + self.formatTime(record, self.datefmt) + Style.RESET_ALL
        # 格式化日志
        return f"{asctime} [{levelname}] {name} | {message}"


def register_logger(name:str,level="DEBUG"):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s",datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

if __name__ == "__main__":
    logger = register_logger("test")
    logger1 = register_logger("test1")
    logger.debug("debug message")
    logger.info("info message")
    logger1.warning("warning message")
    logger1.error("error message")
