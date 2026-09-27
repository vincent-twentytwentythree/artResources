import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import time


def main():
    directory = Path(__file__).resolve().parent
    cards = json.loads((directory / "cards.json").read_text(encoding="utf-8"))
    output = directory / "card_art"
    output.mkdir(exist_ok=True)

    for card in cards:
        card_id = card.get("id")
        if not card_id:
            continue
        destination = output / f"{card_id}.jpg"
        if destination.is_file():
            continue
        url = f"https://art.hearthstonejson.com/v1/512x/{card_id}.jpg"
        time.sleep(0.1)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/jpeg"})
        try:
            with urlopen(request, timeout=15) as response:
                destination.write_bytes(response.read())
        except HTTPError as exc:
            if exc.code != 404:
                raise
            print(f"No art for {card_id}")


if __name__ == "__main__":
    main()
