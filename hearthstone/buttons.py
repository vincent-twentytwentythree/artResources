# Common templates
from zafkiel.ocr import Keyword
from zafkiel.ui import Page
# from zafkiel import Template
from utils.LocalImageTemplate import LocalImageTemplate as Template

diveButton = Template(r"templates/diveButton.png", (0.0, -0.016875), resolution=(2560, 1600), keyword=Keyword('出海'), ocr_mode=1)

# Card page positions from generateLocation.py, relative to the 2560 x 1600 screen center.
card1 = Template(r"templates/rawcard.png", (-0.3125, -0.171875), resolution=(2560, 1600))
card2 = Template(r"templates/rawcard.png", (-0.177734375, -0.171875), resolution=(2560, 1600))
card3 = Template(r"templates/rawcard.png", (-0.04296875, -0.171875), resolution=(2560, 1600))
card4 = Template(r"templates/rawcard.png", (0.091796875, -0.171875), resolution=(2560, 1600))
card5 = Template(r"templates/rawcard.png", (-0.3125, 0.171875), resolution=(2560, 1600))
card6 = Template(r"templates/rawcard.png", (-0.177734375, 0.171875), resolution=(2560, 1600))
card7 = Template(r"templates/rawcard.png", (-0.04296875, 0.171875), resolution=(2560, 1600))
card8 = Template(r"templates/rawcard.png", (0.091796875, 0.171875), resolution=(2560, 1600))
emptyRightTop = Template(r"templates/emptyRightTop.png", (0.1796875, -0.34375), resolution=(2560, 1600))
emptyRightMiddle = Template(r"templates/emptyRightMiddle.png", (0.1796875, 0.025), resolution=(2560, 1600))
cardDetails = Template(r"templates/cardDetails.png", (-0.017578125, -0.125), resolution=(2560, 1600))
