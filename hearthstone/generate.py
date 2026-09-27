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


def match_card_name(text: str, card_names: set[str]):
    """Correct one misread character only when the card name is unambiguous."""
    if text in card_names:
        return text
    if len(text) < 2:
        return None
    matches = [
        name for name in card_names
        if len(name) == len(text)
        and sum(a != b for a, b in zip(name, text)) == 1
    ]
    if len(matches) == 1:
        return matches[0]
    return text

class Generate(UI):
    def __init__(self, config: Config = None):
        self.config = config

    def run(self):
        config_data = self.config.config_data
        page_num = config_data.get("pageNum", 0)
        enableSkip = config_data.get("enableSkip", True)
        if not isinstance(page_num, int) or isinstance(page_num, bool) or page_num < 0:
            raise ValueError("config.json pageNum must be a non-negative integer")

        with CARDS_PATH.open(encoding="utf-8") as cards_file:
            card_data = json.load(cards_file)
        card_names = {
            entry["name"].strip()
            for entry in card_data
            if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"].strip()
        }
        logger.info("cards: {}", len(card_names))

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cards = (card1, card2, card3, card4, card5, card6, card7, card8)

        def position(template):
            width, height = G.DEVICE.get_current_resolution()
            x, y = template.record_pos
            return round(width * (0.5 + x)), round(height * (0.5 + y))

        def checkCard(card):
            retry = 10
            while retry > 0:
                time.sleep(0.1)
                touch(position(emptyCard2Top))
                time.sleep(0.1)
                boxed_results = ocr(card)
                if boxed_results != None and len(boxed_results) > 0:
                    logger.info("card {}", boxed_results)
                    return True
                retry -= 1
            return False

        def card1ZoomOut(default_boxed_results):
            retry = 10
            while retry > 0:
                time.sleep(0.1)
                move(position(emptyCard2Top))
                time.sleep(0.1)
                boxed_results = ocr(card1)
                if boxed_results == None or len(boxed_results) == 0:
                    return True
                for boxed_result in boxed_results:
                    text = boxed_result.text.strip()
                    if text not in default_boxed_results:
                        return True
                retry -= 1
            return False

        def getCardName():
            retry = 10
            while retry > 0:
                retry -= 1
                time.sleep(0.1)
                move(position(emptyCard2Top))
                time.sleep(0.1)
                for cardNameBox in [cardName, cardName2, cardName3]:
                    boxed_results = ocr(cardNameBox, single_line_fallback=True) or []
                    if boxed_results == None or len(boxed_results) == 0:
                        continue
                    logger.debug(boxed_results)

                    for boxed_result in boxed_results:
                        text = boxed_result.text.strip()
                        known_name = match_card_name(text, card_names)
                        if known_name is not None:
                            return known_name
                    if boxed_results != None and len(boxed_results) > 0:
                        return None
            return None

        if enableSkip == True:
            skip_page = page_num
            loop_timer = Timer(0, 100).start()
            while skip_page > 0:
                logger.info("skip {}", page_num - skip_page + 1)
                if loop_timer.reached():
                    raise LoopError('The operation has looped too many times')
                touch(position(emptyRightMiddle))
                skip_page -= 1
                time.sleep(0.1)

        loop_timer = Timer(0, 400).start()
        while True:
            if loop_timer.reached():
                raise LoopError('The operation has looped too many times')
            time.sleep(0.1)
            touch(position(emptyCard2Top))

            default_boxed_results = set([card.text for card in ocr(card1, single_line_fallback=True) if card.text != None and len(card.text) >= 2 and card.text.isdigit() == False])
            logger.info("defaul_boxed_results: {}", default_boxed_results)

            for index, card in enumerate(cards):
                logger.info("card {}", index)
                if checkCard(card) == False:
                    logger.debug(f"{page_num}_{index} no data")
                    continue

                time.sleep(0.1)
                touch(position(card), right_click=True)

                if card1ZoomOut(default_boxed_results) == False:
                    logger.debug(f"{page_num}_{index} card1 zoom out failed")
                    continue

                matched_name = getCardName()
                if matched_name is None:
                    logger.debug(f"{page_num}_{index} ocr failed")
                    continue
                    # raise RuntimeError(f"Card name not found in cards.json on page {page_num}, card {index}")

                PAGE_DATA_DIR = DATA_DIR / f"{page_num}"
                PAGE_DATA_DIR.mkdir(parents=True, exist_ok=True)
                filename =  PAGE_DATA_DIR / f"{matched_name}_{index}.png"
                logger.info(f"{page_num}_{index} new card {filename}")
                try:
                    image = snapshot(cardDetails, str(filename))
                    if image is None:
                        raise RuntimeError(f"Could not save card image: {filename}")
                    if filename is not None and not filename.is_file():
                        aircv.imwrite(filename, image, quality=Config.ST.SNAPSHOT_QUALITY)
                except Exception as e:
                    logger.info(e)
                time.sleep(0.1)
                touch(position(emptyCard2Top))
            time.sleep(0.1)
            touch(position(emptyRightMiddle))
            page_num += 1
            logger.info("next page {}", page_num)
            config_data["pageNum"] = page_num
            temporary_path = CONFIG_PATH.with_suffix(".json.tmp")
            with temporary_path.open("w", encoding="utf-8") as config_file:
                json.dump(config_data, config_file, ensure_ascii=False, indent=4)
                config_file.write("\n")
            os.replace(temporary_path, CONFIG_PATH)
            if config.config_data["debug"] == True:
                break


if __name__ == "__main__":
    config = Config(CONFIG_PATH)
    login = Login(config)
    login.app_start()
    retry = 10
    while retry > 0:
        retry -= 1
        try:
            Generate(config).run()
        except Exception as e:
            logger.error(e)
            time.sleep(10)
        if config.config_data["debug"] == True:
            break
