import datetime
import shutil
import time
from pathlib import Path
import subprocess

from zafkiel import (
    Template,
    logger,
    wait,
    touch,
    stop_app,
    # auto_setup,
    sleep,
    exists,
    find_click,
    Timer,
)
from zafkiel.exception import LoopError
from zafkiel.ocr import Keyword
from zafkiel.ui import UI

from hearthstone.config import Config

from utils.Setup import auto_setup
class Login(UI):
    def __init__(self, config: Config = None):
        self.config = config

    def app_start(self):
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        auto_setup(
            basedir=str(Path.cwd()),
            firing_time=120,
            logdir=f"./log/{date}/report",
            devices=[
                "MessageWindows:///?title_re=.*炉石传说.*",
            ],
        )
        logger.info("App started")

    def app_stop(self):
        stop_app()
        logger.info("App stopped")

    def run(self):
        pass

if __name__ == "__main__":
    config = Config("config_path")
    login = Login(config)
    login.app_start()
    login.run()
