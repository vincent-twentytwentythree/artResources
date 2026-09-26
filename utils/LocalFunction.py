import os
import time
from typing import Optional, Tuple, Type, Callable, Union, List
import threading

from airtest.core.api import *
from airtest import aircv
from airtest.core.cv import try_log_screen
from airtest.core.error import TargetNotFoundError
from airtest.core.helper import G, logwrap, delay_after_operation, set_logdir
from airtest.core.settings import Settings as ST
from airtest.utils.compat import script_log_dir
from pywinauto.findwindows import ElementNotFoundError

# from zafkiel.device.cv import loop_find
from zafkiel.device.template import ImageTemplate as Template
from zafkiel.logger import logger
from zafkiel.exception import NotRunningError, ScriptError
from zafkiel.ocr.ocr import Ocr
from zafkiel.timer import Timer
from zafkiel.utils import random_rectangle_point

import time
from typing import Callable, Tuple, Type

from airtest.core.cv import try_log_screen
from airtest.core.error import TargetNotFoundError
from airtest.core.helper import logwrap, G

from zafkiel.config import Config
from zafkiel.logger import logger
from zafkiel.ocr.ocr import Ocr
from zafkiel.utils import is_color_similar, crop

@logwrap
def touch(
        v: Union[Template, Tuple[int, int]],
        times: int = 1,
        interval: float = 0.05,
        blind: bool = False,
        cls: Type[Ocr] = Ocr,
        v_name: str = None,
        **kwargs
) -> Tuple[int, int]:
    """
    Perform the touch action on the device screen

    Args:
        v: Target to touch, either a ``ImageTemplate`` instance or absolute coordinate (x, y).
        times: How many touches to be performed
        interval: Time interval between two touches.
        blind: Whether to recognize Template, sometimes we only need to click without caring about the image.
        cls: "Ocr" class or its subclass
        v_name: When v is a coordinate, but you want it has a name.
        **kwargs: Platform specific `kwargs`, please refer to corresponding docs.

    Returns:
        Final position to be clicked, e.g. (100, 100)

    Platforms:
        Android, Windows, iOS

    Examples:
        Click absolute coordinates:
            touch((100, 100))
        Click 2 times:
            touch((100, 100), times=2)
        Under Android and Windows platforms, you can set the click duration:
            touch((100, 100), duration=2)
        Right click(Windows):
            touch((100, 100), right_click=True)
    """
    if isinstance(v, Template):
        if blind:
            center_pos = (v.area[2] + v.area[0]) / 2, (v.area[3] + v.area[1]) / 2
        else:
            center_pos = loop_find(v, cls=cls)

        h = v.height * v.ratio()
        w = v.width * v.ratio()  # actual height and width of target in screen
        pos = random_rectangle_point(center_pos, h, w)
    else:
        try_log_screen()
        pos = v
    for _ in range(times):
        G.DEVICE.touch(pos, **kwargs)
        time.sleep(interval)
    delay_after_operation()

    if isinstance(v, Template):
        logger.info((f"Click{pos} {times} times" if times > 1 else f"Click{pos}") + f" @{v.name}")
    elif v_name:
        logger.info((f"Click{pos} {times} times" if times > 1 else f"Click{pos}") + f" @{v_name}")
    else:
        logger.info(f"Click{pos} {times} times" if times > 1 else f"Click{pos}")

    return pos


@logwrap
def find_click(
        rec_template: Template,
        touch_template: Optional[Template] = None,
        times: int = 1,
        interval: float = 0.05,
        timeout: float = 1,
        blind: bool = False,
        cls: Type[Ocr] = Ocr,
) -> bool:
    """
    Find the template image and click it or another image area.

    Args:
        rec_template: "Template" instance to be found.
        touch_template: "ImageTemplate" instance to be clicked, defaults to None which means click rec_template.
        times: How many touches to be performed.
        interval: Time interval between two touches.
        timeout: Time interval to wait for the match.
        blind: Whether to recognize Template, same as parameter of touch().
        cls: "Ocr" class or its subclass

    Returns:
        bool: Whether the target image appear and click it.
    """
    try:
        pos = loop_find(rec_template, timeout, interval=interval, cls=cls)
        h = rec_template.height * rec_template.ratio()
        w = rec_template.width * rec_template.ratio()  # actual height and width of target in screen
        pos = random_rectangle_point(pos, h, w)
    except TargetNotFoundError:
        logger.info(f"<{rec_template.name}> matching failed in {timeout}s")
        return False

    if touch_template:
        touch(touch_template, times, interval, blind, cls)
    else:
        touch(pos, times, interval, v_name=rec_template.name)

    return True


@logwrap
def exists(
        v: Template,
        timeout: float = 0,
        cls: Type[Ocr] = Ocr,
) -> Union[bool, Tuple[int, int]]:
    """
    Check whether given target exists on device screen

    Args:
        v: target to be checked
        timeout: time limit, default is 0 which means loop_find will only search once
        cls: "Ocr" class or its subclass

    Returns:
        False if target is not found, otherwise returns the coordinates of the target

    Platforms:
        Android, Windows, iOS

    Examples:
        if exists(ImageTemplate(r"tpl1606822430589.png")):
            touch(ImageTemplate(r"tpl1606822430589.png"))

        Since ``exists()`` will return the coordinates,
        we can directly click on this return value to reduce one image search:

        pos = exists(ImageTemplate(r"tpl1606822430589.png"))
        if pos:
            touch(pos)
    """
    try:
        pos = loop_find(v, timeout=timeout, cls=cls)
    except TargetNotFoundError:
        logger.info(f"<{v.name}> matching failed in {timeout}s")
        return False
    else:
        return pos


# @logwrap
# def wait(
#         v: Template,
#         timeout: Optional[float] = None,
#         interval: float = 0.3,
#         interval_func: Optional[Callable] = None,
#         cls: Type[Ocr] = Ocr,
# ) -> Tuple[int, int]:
#     """
#     Wait to match the Template on the device screen

#     Args:
#         v: target object to wait for, Template instance
#         timeout: time interval to wait for the match, default is None which is ``ST.FIND_TIMEOUT``
#         interval: time interval in seconds to attempt to find a match
#         interval_func: called after each unsuccessful attempt to find the corresponding match
#         cls: "Ocr" class or its subclass

#     Raises:
#         TargetNotFoundError: raised if target is not found after the time limit expired

#     Returns:
#         coordinates of the matched target

#     Platforms:
#         Android, Windows, iOS

#     Examples:
#         wait(Template(r"tpl1606821804906.png"))  # timeout after ST.FIND_TIMEOUT
#         # find Template every 3 seconds, timeout after 120 seconds
#         wait(Template(r"tpl1606821804906.png"), timeout=120, interval=3)

#         You can specify a callback function every time the search target fails::

#         def notfound():
#             print("No target found")
#         wait(Template(r"tpl1607510661400.png"), interval_func=notfound)
#     """
#     if timeout is None:
#         timeout = ST.FIND_TIMEOUT
#     pos = loop_find(v, timeout, interval=interval, interval_func=interval_func, cls=cls)
#     return pos

@logwrap
def loop_find(
        v,
        timeout: float = Config.ST.FIND_TIMEOUT,
        threshold: float = None,
        interval: float= 0.3,
        interval_func: Callable[[], None] = None,
        cls: Type[Ocr] = Ocr,
) -> Tuple[int, int]:
    """
    Search for image template in the screen until timeout
    Add OCR and color similarity search to airtest.cv.loop_find()

    Args:
        v: image template to be found in screenshot
        timeout: time interval how long to look for the image template
        threshold: default is None
        interval: sleep interval before next attempt to find the image template
        interval_func: function that is executed after unsuccessful attempt to find the image template
        cls: "Ocr" class or its subclass

    Raises:
        TargetNotFoundError: when image template is not found in screenshot

    Returns:
        TargetNotFoundError if image template not found, otherwise returns the position where the image template has
        been found in screenshot
    """
    start_time = time.time()
    while True:
        screen = G.DEVICE.snapshot(filename=None, quality=Config.ST.SNAPSHOT_QUALITY)

        if screen is None:
            logger.warning("Screen is None, may be locked")
        else:
            if threshold:
                v.threshold = threshold

            if not v.rgb or not v.local_search or is_color_similar(v.image, crop(screen, v.area)):
                if v.keyword is not None:
                    ocr = cls(v)
                    ocr_result = ocr.ocr_match_keyword(screen, ocr.button.keyword, direct_ocr=not v.local_search, mode=v.ocr_mode)
                    if ocr_result:
                        if v.local_search:
                            match_pos = int((v.area[0] + v.area[2]) / 2), int((v.area[1] + v.area[3]) / 2)
                            try_log_screen(screen)
                            return match_pos
                        else:
                            for current_ocr_result in ocr_result:
                                x1, y1, x2, y2 = current_ocr_result.area[0], current_ocr_result.area[1], current_ocr_result.area[2], current_ocr_result.area[3]
                                match_pos = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                                if v.rgb and not is_color_similar(v.image, crop(screen, (x1, y1, x2, y2)), 0.5):
                                    continue
                                try_log_screen(screen)
                                return match_pos
                else:
                    match_pos = v.match_in(screen, v.local_search)
                    if match_pos:
                        cost_time = time.time() - start_time
                        logger.debug(f"ImgRec <{v.name}> cost {cost_time:.2f}s: {match_pos}")

                        try_log_screen(screen)
                        return match_pos

        if interval_func is not None:
            interval_func()

        if (time.time() - start_time) > timeout:
            if Config.KEEP_FOREGROUND and not G.DEVICE.is_foreground():
                time.sleep(Config.BUFFER_TIME)
                logger.info("Window covered by another window, bringing to foreground...")
                G.DEVICE.set_foreground()
                start_time = time.time()
                continue

            logger.debug(f"<{v.name}> matching failed in {timeout}s")
            try_log_screen(screen)
            raise TargetNotFoundError(f'Picture {v.filepath} not found on screen')
        else:
            time.sleep(interval)

def move(pos: Union[Template, Tuple[int, int]]) -> Tuple[int, int]:
    """Move the mouse to a coordinate or the center of a template area."""
    if isinstance(pos, Template):
        x1, y1, x2, y2 = pos.area
        pos = (round((x1 + x2) / 2), round((y1 + y2) / 2))
    G.DEVICE.mouse_move(pos)
    return pos


def snapshot(v: Template, filename: str = None):
    """Capture a template area, optionally saving the cropped image."""
    screen = G.DEVICE.snapshot(filename=None, quality=Config.ST.SNAPSHOT_QUALITY)
    if screen is None:
        logger.warning("Screen is None, may be locked")
        return None
    image = crop(screen, v.area)
    if filename is not None:
        aircv.imwrite(filename, image, quality=Config.ST.SNAPSHOT_QUALITY)
    return image
