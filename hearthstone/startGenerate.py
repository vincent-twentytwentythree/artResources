import json
import os
import time
from pathlib import Path

from airtest.core.helper import G
from zafkiel import Timer
from zafkiel.exception import LoopError
from zafkiel.ui import UI

from hearthstone.config import Config
from hearthstone.buttons import (
    card1, card2, card3, card4, card5, card6, card7, card8,
    cardDetails, emptyRightTop, emptyRightMiddle,
)
from hearthstone.login import Login
from utils.LocalFunction import touch, move, snapshot
from zafkiel.logger import logger

CONFIG_PATH = Path(__file__).with_name("config.json")
DATA_DIR = Path(__file__).with_name("data")


class StartGenerate(UI):
    def __init__(self, config: Config = None):
        self.config = config

    def run(self):
        with CONFIG_PATH.open(encoding="utf-8") as config_file:
            config_data = json.load(config_file)
        page_num = config_data.get("pageNum", 0)
        if not isinstance(page_num, int) or isinstance(page_num, bool) or page_num < 0:
            raise ValueError("config.json pageNum must be a non-negative integer")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cards = (card1, card2, card3, card4, card5, card6, card7, card8)

        def position(template):
            width, height = G.DEVICE.get_current_resolution()
            x, y = template.record_pos
            return round(width * (0.5 + x)), round(height * (0.5 + y))

        # skip_page = page_num
        # loop_timer = Timer(0, 100).start()
        # while skip_page > 0:
        #     logger.info("skip {}", page_num - skip_page + 1)
        #     if loop_timer.reached():
        #         raise LoopError('The operation has looped too many times')
        #     touch(position(emptyRightMiddle))
        #     skip_page -= 1
        #     time.sleep(0.5)

        loop_timer = Timer(0, 450).start()
        while True:
            if loop_timer.reached():
                raise LoopError('The operation has looped too many times')

            for index, card in enumerate(cards):
                touch(position(card), right_click=True)
                move(position(emptyRightTop))
                filename = DATA_DIR / f"{page_num}_{index}.png"
                if snapshot(cardDetails, str(filename)) is None or not filename.is_file():
                    raise RuntimeError(f"Could not save card image: {filename}")
                touch(position(emptyRightTop))
                time.sleep(0.1)
            touch(position(emptyRightMiddle))
            page_num += 1
            config_data["pageNum"] = page_num
            temporary_path = CONFIG_PATH.with_suffix(".json.tmp")
            with temporary_path.open("w", encoding="utf-8") as config_file:
                json.dump(config_data, config_file, ensure_ascii=False, indent=4)
                config_file.write("\n")
            os.replace(temporary_path, CONFIG_PATH)
            time.sleep(0.5)


if __name__ == "__main__":
    config = Config(str(CONFIG_PATH))
    login = Login(config)
    login.app_start()
    StartGenerate(config).run()
