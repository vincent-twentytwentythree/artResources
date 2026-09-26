# Common template
from pathlib import Path

from zafkiel.ocr import Keyword
from zafkiel.ui import Page
# from zafkiel import Template
from utils.LocalImageTemplate import LocalImageTemplate as Template

# Card page positions from generateLocation.py, relative to the 2560 x 1600 screen center.
card1 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (-0.3125, -0.171875), resolution=(2560, 1600))
card2 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (-0.177734375, -0.171875), resolution=(2560, 1600))
card3 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (-0.04296875, -0.171875), resolution=(2560, 1600))
card4 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (0.091796875, -0.171875), resolution=(2560, 1600))
card5 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (-0.3125, 0.171875), resolution=(2560, 1600))
card6 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (-0.177734375, 0.171875), resolution=(2560, 1600))
card7 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (-0.04296875, 0.171875), resolution=(2560, 1600))
card8 = Template(str(Path(__file__).parent / "template" / "rawcard.png"), (0.091796875, 0.171875), resolution=(2560, 1600))
emptyRightTop = Template(str(Path(__file__).parent / "template" / "emptyRightTop.png"), (0.1796875, -0.34375), resolution=(2560, 1600))
emptyMiddleTop = Template(str(Path(__file__).parent / "template" / "emptyMiddleTop.png"), (-0.024609375, -0.425), resolution=(2560, 1600))
emptyCard2Top = Template(str(Path(__file__).parent / "template" / "emptyCard2Top.png"), (-0.177734375, -0.34375), resolution=(2560, 1600))
emptyRightMiddle = Template(str(Path(__file__).parent / "template" / "emptyRightMiddle.png"), (0.1796875, 0.025), resolution=(2560, 1600))
cardDetails = Template(
    str(Path(__file__).parent / "template" / "cardDetails.png"),
    (-0.024609375, -0.13375),
    resolution=(2560, 1600),
)
cardName = Template(
    str(Path(__file__).parent / "template" / "cardName.png"),
    (-0.024609375, -0.110625),
    resolution=(2560, 1600),
)
cardName2 = Template(
    str(Path(__file__).parent / "template" / "cardName2.png"),
    (-0.024609375, -0.076875),
    resolution=(2560, 1600),
)
cardName3 = Template(
    str(Path(__file__).parent / "template" / "cardName3.png"),
    (-0.024609375, 0.055),
    resolution=(2560, 1600),
)
