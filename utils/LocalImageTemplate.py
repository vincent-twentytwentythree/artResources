import os
import types
from functools import cached_property
from pathlib import Path
from typing import Optional, Tuple

import cv2
from airtest.core.cv import Template, MATCHING_METHODS
from airtest.core.error import InvalidMatchingMethodError
from airtest.core.helper import G, logwrap
from airtest.utils.transform import TargetPos
from numpy import ndarray

from zafkiel.config import Config
from zafkiel.ocr.keyword import Keyword
from zafkiel.device.template import ImageTemplate


class LocalImageTemplate(ImageTemplate):
    def __init__(
            self,
            filename: str,
            record_pos: Optional[Tuple[float, float]] = None,
            keyword: Optional[Keyword] = None,
            resolution: Tuple[int, int] = (1280, 720),
            rgb: bool = False,
            local_search: bool = True,
            ocr_mode: int = 0,
            template_path: str = 'templates',
            threshold: Optional[float] = None,
            target_pos: int = TargetPos.MID,
            scale_max: int = 800,
            scale_step: float = 0.005
    ):
        super().__init__(filename, record_pos, keyword, resolution, rgb, local_search, ocr_mode, template_path, threshold, target_pos, scale_max, scale_step)

    @cached_property
    def border(self) -> tuple[int, int, int]:
        return 0, 0, 0

    @cached_property
    def area(self) -> tuple:
        """
        Calculate the area of the template image on the current screen.

        Returns:
            Upper left and lower right corner coordinate.
        """
        screen_resolution = G.DEVICE.get_current_resolution()

        screen_width = screen_resolution[0] - self.border[1] * 2
        screen_height = screen_resolution[1] - self.border[0] - self.border[2]

        ratio = self.ratio(screen_height)
        x1 = screen_width / 2 + self.record_pos[0] * screen_width - self.width / 2 * ratio + self.border[1]
        y1 = screen_height / 2 + self.record_pos[1] * screen_height - self.height / 2 * ratio + self.border[0]
        x2 = screen_width / 2 + self.record_pos[0] * screen_width + self.width / 2 * ratio + self.border[1]
        y2 = screen_height / 2 + self.record_pos[1] * screen_height + self.height / 2 * ratio + self.border[0]
        return x1, y1, x2, y2
