import time

from zafkiel import Template, logger, Timer, exists, find_click, swipe
from zafkiel.exception import LoopError
from zafkiel.ocr import Keyword
from zafkiel.ui import UI

from config import Config
from hearthstone.buttons import *
from hearthstone.login import Login
from utils.LocalFunction import touch
import random

class StartGenerate(UI):
    def __init__(self, config: Config = None):
        self.config = config

    # read from config.json
    pageNum = 0

    def run(self):

        loop_timer = Timer(0, 100).start()
        while True:
            if loop_timer.reached():
                raise LoopError('The operation has looped too many times')

            for card in [card1, card2, card3, card4, card5, card6, card7, card8]:
                touch(card, right_click=True)
                # move(emptyRightTop)
                # snapshot(cardDetails)
                touch(emptyRightTop)
                time.sleep(0.1)
            emptyRightMiddle
            pageNum = pageNum + 1
            # write to config.json

if __name__ == "__main__":
    config = Config("config_path")
    login = Login(config)
    login.app_start()
    StartGenerate(config).run()
