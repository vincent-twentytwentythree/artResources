"""Export readable Unity objects from OSX bundles into OSX_extract.

Run: conda run -n unity --no-capture-output python -u export_unity_readable.py OSX OSX_extract
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import re
import sys
import warnings

import UnityPy
from PIL import Image
from UnityPy.helpers.ResourceReader import get_resource_data


UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.0f1"
warnings.filterwarnings("ignore", category=UnityPy.exceptions.UnityVersionFallbackWarning)

MEDIA_TYPES = {"Texture2D", "Sprite", "AudioClip", "VideoClip", "Mesh", "Shader", "TextAsset"}
SAFE_NAME = re.compile(r"[^\w.() -]+", re.UNICODE)


def filename(name: str, path_id: int, extension: str) -> str:
    clean = SAFE_NAME.sub("_", str(name or "unnamed")).strip(" ._")[:120] or "unnamed"
    return f"{clean}__{path_id}{extension}"


def json_default(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "value"):
        return value.value
    return str(value)


def write_data(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def export_media(obj, kind: str, data, root: Path) -> list[str]:
    name = getattr(data, "m_Name", kind)
    folder = root / kind
    folder.mkdir(parents=True, exist_ok=True)
    outputs = []
    if kind in ("Texture2D", "Sprite"):
        if kind == "Texture2D" and (data.m_Width == 0 or data.m_Height == 0):
            return []
        if kind == "Texture2D" and data.m_TextureFormat == 74:
            # Unity RGBA64 stores little-endian 16-bit channels. Pillow cannot
            # open that format directly, so take the high byte of each channel.
            width, height = data.m_Width, data.m_Height
            raw = data.get_image_data()
            needed = width * height * 8
            if len(raw) < needed:
                raise ValueError(f"RGBA64 data is short: {len(raw)} < {needed}")
            image = Image.frombytes("RGBA", (width, height), bytes(raw[1:needed:2]))
            image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        else:
            image = data.image
        path = folder / filename(name, obj.path_id, ".png")
        image.save(path, format="PNG", compress_level=1)
        outputs.append(path)
    elif kind == "AudioClip":
        for sample_name, sample_data in data.samples.items():
            extension = Path(sample_name).suffix or ".bin"
            path = folder / filename(Path(sample_name).stem, obj.path_id, extension)
            write_data(path, sample_data)
            outputs.append(path)
    elif kind == "VideoClip":
        resource = data.m_ExternalResources
        payload = get_resource_data(
            resource.m_Source,
            data.object_reader.assets_file,
            resource.m_Offset,
            resource.m_Size,
        )
        if payload[4:8] == b"ftyp":
            extension = ".mp4"
        elif payload[:4] == b"\x1a\x45\xdf\xa3":
            extension = ".webm"
        else:
            extension = Path(data.m_OriginalPath).suffix or ".bin"
        path = folder / filename(name, obj.path_id, extension)
        write_data(path, payload)
        outputs.append(path)
    elif kind == "Mesh":
        text = data.export("obj")
        if text:
            path = folder / filename(name, obj.path_id, ".obj")
            write_data(path, text)
            outputs.append(path)
        else:
            path = folder / filename(name, obj.path_id, ".json")
            write_data(path, json.dumps(obj.read_typetree(), ensure_ascii=False, default=json_default))
            outputs.append(path)
    elif kind == "Shader":
        try:
            path = folder / filename(name, obj.path_id, ".shader.txt")
            write_data(path, data.export())
        except Exception:
            path = folder / filename(name, obj.path_id, ".json")
            write_data(path, json.dumps(obj.read_typetree(), ensure_ascii=False, default=json_default))
        outputs.append(path)
    elif kind == "TextAsset":
        script = data.m_Script
        extension = Path(name).suffix.lower()
        if extension not in {".json", ".xml", ".csv", ".txt", ".yaml", ".yml", ".ini", ".html", ".js"}:
            extension = ".txt"
        path = folder / filename(Path(name).stem, obj.path_id, extension)
        write_data(path, script)
        outputs.append(path)
    return [str(path.relative_to(root)) for path in outputs]


def export_bundle(source: Path, target: Path) -> tuple[Counter, Counter, list[dict]]:
    root = target / source.stem / "readable"
    root.mkdir(parents=True, exist_ok=True)
    environment = UnityPy.load(str(source))
    objects = list(environment.objects)
    type_counts = Counter()
    file_counts = Counter()
    errors = []
    with (root / "objects.jsonl").open("w", encoding="utf-8") as index:
        for obj in objects:
            kind = obj.type.name
            type_counts[kind] += 1
            entry = {"path_id": obj.path_id, "type": kind, "byte_size": obj.byte_size}
            try:
                if kind in MEDIA_TYPES:
                    data = obj.read()
                    entry["name"] = getattr(data, "m_Name", "")
                    entry["files"] = export_media(obj, kind, data, root)
                    file_counts[kind] += len(entry["files"])
                    if kind == "Texture2D":
                        entry["size"] = [data.m_Width, data.m_Height]
                    elif kind == "VideoClip":
                        entry["size"] = [data.Width, data.Height]
                        entry["original_path"] = data.m_OriginalPath
                    elif kind == "AudioClip":
                        entry["channels"] = data.m_Channels
                        entry["frequency"] = data.m_Frequency
                    elif kind == "Mesh":
                        entry["vertices"] = getattr(getattr(data, "m_VertexData", None), "m_VertexCount", None)
                else:
                    tree = obj.read_typetree()
                    entry["name"] = tree.get("m_Name", "") if isinstance(tree, dict) else ""
                    entry["data"] = tree
            except Exception as error:
                entry["error"] = f"{type(error).__name__}: {error}"
                errors.append({"path_id": obj.path_id, "type": kind, "error": entry["error"]})
            index.write(json.dumps(entry, ensure_ascii=False, default=json_default) + "\n")
    (root / "bundle_report.json").write_text(
        json.dumps(
            {"source": source.name, "objects": len(objects), "types": type_counts,
             "exported_files": file_counts, "errors": errors},
            indent=2, ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    (root / ".complete").write_text(source.name + "\n")
    return type_counts, file_counts, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--repair-errors", action="store_true")
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error("--shard must be between 0 and --shards - 1")
    sources = sorted(args.source.glob("*.unity3d"))
    if args.limit:
        sources = sources[:args.limit]
    sources = [source for index, source in enumerate(sources) if index % args.shards == args.shard]
    report_path = args.target / (
        "readable_report.json" if args.shards == 1 else f"readable_report_shard_{args.shard}.json"
    )
    type_counts = Counter()
    file_counts = Counter()
    errors = []
    bundle_failures = []
    completed = skipped = 0
    for index, source in enumerate(sources, 1):
        root = args.target / source.stem / "readable"
        if (root / ".complete").exists():
            needs_repair = False
            if args.repair_errors:
                try:
                    needs_repair = bool(json.loads((root / "bundle_report.json").read_text())["errors"])
                except (OSError, KeyError, ValueError):
                    needs_repair = True
            if not needs_repair:
                skipped += 1
                continue
        try:
            types, files, bundle_errors = export_bundle(source, args.target)
            type_counts.update(types)
            file_counts.update(files)
            errors.extend({"bundle": source.name, **error} for error in bundle_errors)
            completed += 1
        except Exception as error:
            bundle_failures.append({"bundle": source.name, "error": f"{type(error).__name__}: {error}"})
            print(f"FAILED {source.name}: {error}", file=sys.stderr, flush=True)
        if index % 50 == 0 or index == len(sources):
            print(f"{index}/{len(sources)} bundles, complete={completed}, skipped={skipped}, "
                  f"object errors={len(errors)}, bundle failures={len(bundle_failures)}", flush=True)
        if index % 100 == 0 or index == len(sources):
            report_path.write_text(
                json.dumps({"source_bundles": len(sources), "processed": index,
                            "completed_this_run": completed, "skipped": skipped,
                            "object_types_this_run": type_counts,
                            "exported_files_this_run": file_counts,
                            "object_errors": errors,
                            "bundle_failures": bundle_failures},
                           indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    return 1 if bundle_failures or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
