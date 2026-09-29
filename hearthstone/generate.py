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
        if hasattr(G.DEVICE, "screen_capture_available") and not G.DEVICE.screen_capture_available():
            raise RuntimeError(
                "macOS Screen Recording permission is required for card OCR and PNG capture. "
                "Allow the terminal running Python in System Settings > Privacy & Security > Screen Recording."
            )
        config_data = self.config.config_data
        page_num = config_data.get("pageNum", 0)
        sleep_time = config_data.get("sleepTime", 0.2)
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
        saved_card_names = {}
        for saved_png in DATA_DIR.glob("*/*.png"):
            saved_card_names[saved_png.name] = saved_png.parent
        cards = (card1, card2, card3, card4, card5, card6, card7, card8)

        previous_card1_box = None
        previous_card1_name = None

        def card1_texts(boxed_results):
            result = set()
            for box in (boxed_results or []):
                if box.text is None:
                    continue
                text = box.text.strip()
                if len(text) >= 2 and not text.isdigit():
                    result.add(text)
            return result

        def position(template):
            width, height = G.DEVICE.get_current_resolution()
            x, y = template.record_pos
            return round(width * (0.5 + x)), round(height * (0.5 + y))

        def checkCard(card):
            retry = 10
            while retry > 0:
                time.sleep(sleep_time)
                touch(position(emptyCard2Top))
                time.sleep(sleep_time)
                boxed_results = ocr(card)
                if boxed_results != None and len(boxed_results) > 0:
                    logger.info("card {}", boxed_results)
                    return True
                retry -= 1
            return False

        def card1ZoomOut(default_boxed_results):
            retry = 10
            while retry > 0:
                time.sleep(sleep_time)
                move(position(emptyCard2Top))
                time.sleep(sleep_time)
                boxed_results = ocr(card1, need_crop=False)
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
                time.sleep(sleep_time)
                move(position(emptyCard2Top))
                time.sleep(sleep_time)
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

        def jump_newPage():
            nonlocal page_num, previous_card1_box, previous_card1_name
            retry = 10
            while retry > 0:
                time.sleep(sleep_time)
                touch(position(emptyRightMiddle))
                time.sleep(sleep_time * 3)
                touch(position(emptyCard2Top))
                time.sleep(sleep_time)
                boxed_results = ocr(card1, single_line_fallback=True, need_crop=False)
                current_card1_box = card1_texts(boxed_results)
                if current_card1_box and len((previous_card1_box or set()) & current_card1_box) < 2 and previous_card1_name not in current_card1_box:
                    break
                logger.debug(f"{page_num} next page card1 same as previous page card1 name")
                retry -= 1
            if retry == 0:
                raise RuntimeError(f"Could not advance to next page after 10 attempts")

        def handle_page():
            nonlocal page_num, previous_card1_box, previous_card1_name
            time.sleep(sleep_time)
            touch(position(emptyCard2Top))

            default_boxed_results = card1_texts(ocr(card1, single_line_fallback=True, need_crop=False))
            logger.info("defaul_boxed_results: {}", default_boxed_results)
            if not default_boxed_results:
                logger.debug(f"{page_num} card1 ocr failed")
                return

            if len((previous_card1_box or set()) & default_boxed_results) >= 2 or previous_card1_name in default_boxed_results:
                jump_newPage()
                return
            else:
                logger.info("previous_card1_name: {} previous_card1_box: {}, default_boxed_results: {}", previous_card1_name, previous_card1_box, default_boxed_results)

            captured_cards = 0
            logger.info("page {}, previous_card1_box: {}", page_num, previous_card1_box)
            for index, card in enumerate(cards):
                logger.info("card {}", index)
                if checkCard(card) == False:
                    logger.debug(f"{page_num}_{index} no data")
                    continue

                time.sleep(sleep_time)
                touch(position(card), right_click=True)

                if card1ZoomOut(default_boxed_results) == False:
                    logger.debug(f"{page_num}_{index} card1 zoom out failed")
                    continue

                matched_name = getCardName()
                if matched_name is None:
                    logger.debug(f"{page_num}_{index} ocr failed")
                    continue
                    # raise RuntimeError(f"Card name not found in cards.json on page {page_num}, card {index}")

                if index == 0 and previous_card1_name == matched_name:
                    jump_newPage()
                    return
                if index == 0:
                    previous_card1_name = matched_name

                page_data_dir = DATA_DIR / str(page_num)
                card_filename = f"{matched_name}_{index}.png"
                if enableSkip and captured_cards == 0:
                    saved_page = saved_card_names.get(card_filename)
                    if saved_page is not None and saved_page.exists():
                        if saved_page == page_data_dir:
                            logger.info("skipping saved page {} for card {}", saved_page, card_filename)
                            break
                        if page_data_dir.exists():
                            raise RuntimeError(f"Cannot move {saved_page} to occupied page directory {page_data_dir}")
                        saved_page.rename(page_data_dir)
                        for saved_png in page_data_dir.glob("*.png"):
                            saved_card_names[saved_png.name] = page_data_dir
                        logger.info("moved saved page {} to {}", saved_page, page_data_dir)
                        break

                page_data_dir.mkdir(parents=True, exist_ok=True)
                filename = page_data_dir / card_filename
                logger.info(f"{page_num}_{index} new card {filename}")
                if filename is not None and not filename.is_file():
                    image = snapshot(cardDetails)
                    aircv.imwrite(str(filename), image, quality=self.config.config_data.get("SNAPSHOT_QUALITY", 10))
                    if image is None or not filename.is_file():
                        raise RuntimeError(f"Could not save card image: {filename}")
                    saved_card_names[card_filename] = page_data_dir
                captured_cards += 1
                time.sleep(sleep_time)
                touch(position(emptyCard2Top))
            page_data_dir = DATA_DIR / str(page_num)
            if not page_data_dir.is_dir():
                raise RuntimeError(f"Page data directory does not exist: {page_data_dir}")
            previous_card1_box = default_boxed_results
            jump_newPage()
            page_num += 1
            logger.info("next page {}", page_num)
            config_data["pageNum"] = page_num
            temporary_path = CONFIG_PATH.with_suffix(".json.tmp")
            with temporary_path.open("w", encoding="utf-8") as config_file:
                json.dump(config_data, config_file, ensure_ascii=False, indent=4)
                config_file.write("\n")
            os.replace(temporary_path, CONFIG_PATH)

        loop_timer = Timer(0, 400).start()
        while True:
            time.sleep(sleep_time)
            if loop_timer.reached():
                raise LoopError('The operation has looped too many times')
            handle_page()
            if self.config.config_data["debug"] == True:
                return

if __name__ == "__main__":
    config = Config(CONFIG_PATH)
    login = Login(config)
    login.app_start()
    try:
        Generate(config).run()
    except Exception as e:
        logger.error(e)
