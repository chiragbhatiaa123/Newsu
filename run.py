from src.utils.logger import setup_logger
from src.bot import run_bot
from src.keep_alive import keep_alive

if __name__ == '__main__':
    setup_logger()
    keep_alive()
    run_bot()
