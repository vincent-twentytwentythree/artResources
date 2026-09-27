"""Inspect OCR on a saved card-name crop without starting the game."""

import argparse
from pathlib import Path

import cv2
from pponnxcr import TextSystem


DEFAULT_IMAGE = Path(__file__).resolve().parent.parent / "debug" / "ocr_1790452924208213500.png"

def read_image(path: Path):
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", type=Path, default=DEFAULT_IMAGE)
    args = parser.parse_args()

    image = read_image(args.image)
    model = TextSystem("zhs")
    raw_detected = model.detect_and_ocr(image)
    # The card name touches the crop edges. Give the detector context while
    # preserving the edge colors; a black border changes those colors.
    padded = cv2.copyMakeBorder(image, 16, 16, 16, 16, cv2.BORDER_REPLICATE)
    detected = model.detect_and_ocr(padded)
    padded_8 = cv2.copyMakeBorder(image, 8, 8, 8, 8, cv2.BORDER_REPLICATE)
    detected_8 = model.detect_and_ocr(padded_8)
    relaxed = model.detect_and_ocr(image, box_thresh=0.5)
    print(f"Image: {args.image.resolve()} ({image.shape[1]}x{image.shape[0]})")
    print(f"Raw detection: {[(item.text, item.score) for item in raw_detected]}")
    print(f"16px padded detection: {[(item.text, item.score) for item in detected]}")
    print(f"8px padded detection: {[(item.text, item.score) for item in detected_8]}")
    print(f"Lower box threshold (0.5): {[(item.text, item.score) for item in relaxed]}")

    # A tight, curved card-title crop can defeat detection even when the
    # recognizer can read its single line directly.
    recognized, _ = model.text_recognizer([image])
    print(f"Direct recognition: {recognized}")

if __name__ == "__main__":
    main()
