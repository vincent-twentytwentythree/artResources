import csv
import json
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent
    cards = json.loads((directory / "cards.json").read_text(encoding="utf-8"))

    # Include fields that appear on any card, preserving their first-seen order.
    fields = list(dict.fromkeys(key for card in cards for key in card))
    fields = [field for field in fields if field != "photoUrl"] + ["photoUrl"]

    with (directory / "card.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()

        for card in cards:
            row = {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in card.items()
            }
            card_id = card.get("id")
            row["photoUrl"] = None
            if card_id:
                for extension in ("png", "jpg"):
                    photo = directory / "card_art" / f"{card_id}.{extension}"
                    if photo.is_file():
                        row["photoUrl"] = f"card_art/{card_id}.{extension}"
                        break
            writer.writerow(row)


if __name__ == "__main__":
    main()
