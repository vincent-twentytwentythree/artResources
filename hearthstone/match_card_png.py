"""Match Hearthstone card IDs to extracted Unity portrait PNGs.

The carddef GameObject name is the card ID. Its portrait component stores an
asset GUID, and each texture bundle's AssetBundle container maps that GUID to a
Texture2D object. This avoids guessing from similar image filenames.

Run `python match_card_png.py` for a dry run, or add `--write` to update card.csv.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile


def card_portrait_guids(root: Path, wanted_ids: set[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for index_file in root.glob("carddef*/readable/objects.jsonl"):
        objects = [json.loads(line) for line in index_file.open(encoding="utf-8")]
        game_objects = {
            obj["path_id"]: obj.get("name", "")
            for obj in objects
            if obj["type"] == "GameObject"
        }
        for obj in objects:
            if obj["type"] != "MonoBehaviour":
                continue
            fields = obj.get("data", {})
            portrait = fields.get("m_PortraitTexturePath", "")
            if ":" not in portrait:
                continue
            game_object_id = fields.get("m_GameObject", {}).get("m_PathID")
            card_id = game_objects.get(game_object_id, "")
            if card_id in wanted_ids:
                result[card_id].add(portrait.rsplit(":", 1)[1].lower())
    return result


def texture_paths_by_guid(root: Path, wanted_guids: set[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for report_file in root.glob("*/readable/bundle_report.json"):
        report = json.loads(report_file.read_text(encoding="utf-8"))
        if not report.get("types", {}).get("Texture2D"):
            continue
        readable = report_file.parent
        textures: dict[int, str] = {}
        containers = []
        with (readable / "objects.jsonl").open(encoding="utf-8") as index:
            for line in index:
                if '"type": "Texture2D"' in line:
                    obj = json.loads(line)
                    if obj.get("files"):
                        png = readable / obj["files"][0]
                        if png.is_file():
                            textures[obj["path_id"]] = png.as_posix()
                elif '"type": "AssetBundle"' in line:
                    containers = json.loads(line)["data"].get("m_Container", [])
        for guid, item in containers:
            guid = guid.lower()
            if guid not in wanted_guids:
                continue
            path_id = item.get("asset", {}).get("m_PathID")
            png = textures.get(path_id)
            if png:
                result[guid].add(png)
    return result


def choose_path(paths: set[str]) -> str:
    if not paths:
        return ""
    if len(paths) == 1:
        return next(iter(paths))
    hashes = {hashlib.sha256(Path(path).read_bytes()).digest() for path in paths}
    if len(hashes) != 1:
        return ""
    return sorted(paths, key=lambda path: ("_global" not in path, path))[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("card.csv"))
    parser.add_argument("--extract", type=Path, default=Path("OSX_extract"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    has_bom = args.csv.read_bytes().startswith(b"\xef\xbb\xbf")
    with args.csv.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if "id" not in fields:
        raise ValueError("card.csv has no id column")
    if any(None in row for row in rows):
        raise ValueError("card.csv has rows wider than its header")

    links = card_portrait_guids(args.extract, {row["id"] for row in rows})
    needed_guids = {guid for values in links.values() for guid in values}
    textures = texture_paths_by_guid(args.extract, needed_guids)
    statuses = Counter()
    assignments = {}
    for row in rows:
        card_id = row["id"]
        guids = links.get(card_id, set())
        if not guids:
            statuses["no_portrait_link"] += 1
            continue
        if len(guids) != 1:
            statuses["multiple_portrait_guids"] += 1
            continue
        paths = textures.get(next(iter(guids)), set())
        path = choose_path(paths)
        if path:
            assignments[card_id] = path
            statuses["matched"] += 1
        elif paths:
            statuses["conflicting_pngs"] += 1
        else:
            statuses["png_not_extracted"] += 1

    print(json.dumps(dict(statuses), indent=2))
    print("Example LT22_023E3_01:", assignments.get("LT22_023E3_01", ""))
    if not args.write:
        return

    if "original_png_path" not in fields:
        fields.append("original_png_path")
    for row in rows:
        row["original_png_path"] = assignments.get(row["id"], "")

    handle, temporary = tempfile.mkstemp(prefix=".card_png_", suffix=".csv", dir=args.csv.parent)
    try:
        os.chmod(temporary, args.csv.stat().st_mode & 0o777)
        with os.fdopen(handle, "w", encoding="utf-8-sig" if has_bom else "utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        with Path(temporary).open(encoding="utf-8-sig", newline="") as file:
            written = list(csv.DictReader(file))
        if len(written) != len(rows) or any(
            any(before.get(field) != after.get(field) for field in fields)
            for before, after in zip(rows, written)
        ):
            raise ValueError("CSV round-trip validation failed")
        os.replace(temporary, args.csv)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


if __name__ == "__main__":
    main()
