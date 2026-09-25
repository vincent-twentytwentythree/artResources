buttonsForHomePage = {
    "diveButton": (1280, 773),
}

# Pixel centers in template/rawpage.png (2560 x 1600).
# Cards are numbered left to right, top row before bottom row.
cardPageLocations = {
    "card1": (480, 525),
    "card2": (825, 525),
    "card3": (1170, 525),
    "card4": (1515, 525),
    "card5": (480, 1075),
    "card6": (825, 1075),
    "card7": (1170, 1075),
    "card8": (1515, 1075),
    "emptyRightTop": (1740, 250),
    "emptyRightMiddle": (1740, 840),
    "cardDetails": (1235, 600)
}

def getAllRelatePos(buttonName, location):
    width, height = (2560, 1600)
    x, y = location

    record_pos = (
        (x - width / 2) / width,
        (y - height / 2) / height
    )
    print(buttonName, record_pos)
    return record_pos


buttonsForHomePageRelatePos = {
    name: getAllRelatePos(name, pos)
    for name, pos in buttonsForHomePage.items()
}

cardPageRelatePos = {
    name: getAllRelatePos(name, pos)
    for name, pos in cardPageLocations.items()
}
