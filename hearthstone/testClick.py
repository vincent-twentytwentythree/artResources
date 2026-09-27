import json
import os
import time
from pathlib import Path

from airtest.core.helper import G
from zafkiel import Timer
from zafkiel.exception import LoopError
from zafkiel.ui import UI
from airtest import aircv
from hearthstone.config import Config
from hearthstone.buttons import (
    card1, card2, card3, card4, card5, card6, card7, card8,
    cardDetails, emptyRightTop, emptyRightMiddle, cardName, cardName2, cardName3, emptyCard2Top,
    emptyMiddleTop
)
from hearthstone.login import Login
from utils.LocalFunction import touch, move, snapshot, ocr
from zafkiel.logger import logger

CONFIG_PATH = Path(__file__).with_name("config.json")
CARDS_PATH = Path(__file__).with_name("cards.json")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def position(template):
    width, height = G.DEVICE.get_current_resolution()
    x, y = template.record_pos
    return round(width * (0.5 + x)), round(height * (0.5 + y))

def checkCard():
    touch(position(emptyCard2Top))
    time.sleep(0.1)
    touch(position(card1), right_click=True)
    time.sleep(0.1)
    touch(position(card1))
    move(position(emptyCard2Top))

if __name__ == "__main__":
    config = Config(CONFIG_PATH)
    login = Login(config)
    login.app_start()
    checkCard()
