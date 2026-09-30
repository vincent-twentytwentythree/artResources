"""Extract the files stored inside every UnityFS bundle in a directory.

Run with: conda run -n unity python extract_unity_bundles.py OSX OSX_extract
Requires the lz4 package (installed with UnityPy in the unity environment).
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path, PurePosixPath

import lz4.block


def read_exact(stream, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f"Unexpected end of file: wanted {size}, got {len(data)}")
    return data


def cstring(stream) -> str:
    data = bytearray()
    while True:
        char = read_exact(stream, 1)
        if char == b"\0":
            return data.decode("utf-8")
        data.extend(char)


def unpack_block(data: bytes, expected_size: int, flags: int) -> bytes:
    compression = flags & 0x3F
    if compression == 0:
        result = data
    elif compression in (2, 3):
        result = lz4.block.decompress(data, uncompressed_size=expected_size)
    else:
        raise ValueError(f"Unsupported UnityFS compression type {compression}")
    if len(result) != expected_size:
        raise ValueError(f"Decompressed size {len(result)} != {expected_size}")
    return result


def align16(stream) -> None:
    stream.seek((-stream.tell()) % 16, os.SEEK_CUR)


def extract_bundle(source: Path, target_root: Path) -> tuple[int, int]:
    with source.open("rb") as stream:
        if cstring(stream) != "UnityFS":
            raise ValueError("Expected UnityFS signature")
        version = struct.unpack(">I", read_exact(stream, 4))[0]
        cstring(stream)  # player version
        cstring(stream)  # engine version
        total_size, info_size, info_uncompressed_size, flags = struct.unpack(
            ">QIII", read_exact(stream, 20)
        )
        if version != 8 or flags != 0x243:
            raise ValueError(f"Unexpected UnityFS version/flags: {version}/{flags:#x}")
        if total_size != source.stat().st_size:
            raise ValueError("Bundle size in header does not match the file")
        align16(stream)
        info = unpack_block(read_exact(stream, info_size), info_uncompressed_size, flags)
        # 0x200 means block data starts at the next 16-byte boundary.
        align16(stream)
        position = 16  # skip block data hash
        block_count = struct.unpack_from(">I", info, position)[0]
        position += 4
        blocks = []
        for _ in range(block_count):
            raw_size, packed_size, block_flags = struct.unpack_from(">IIH", info, position)
            blocks.append((raw_size, packed_size, block_flags))
            position += 10
        node_count = struct.unpack_from(">I", info, position)[0]
        position += 4
        nodes = []
        for _ in range(node_count):
            offset, size, _node_flags = struct.unpack_from(">QQI", info, position)
            position += 20
            end = info.index(b"\0", position)
            name = info[position:end].decode("utf-8")
            position = end + 1
            path = PurePosixPath(name)
            if path.is_absolute() or not path.parts or ".." in path.parts:
                raise ValueError(f"Unsafe internal path: {name!r}")
            nodes.append((offset, size, path))
        nodes.sort(key=lambda item: item[0])
        bundle_root = target_root / source.stem
        bundle_root.mkdir(parents=True, exist_ok=True)
        output_files = []
        for _offset, _size, path in nodes:
            dest = bundle_root.joinpath(*path.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            output_files.append(dest.open("wb"))
        try:
            raw_position = 0
            current_node = 0
            for raw_size, packed_size, block_flags in blocks:
                raw = unpack_block(read_exact(stream, packed_size), raw_size, block_flags)
                block_end = raw_position + raw_size
                while current_node < node_count:
                    offset, size, _path = nodes[current_node]
                    end = offset + size
                    if offset >= block_end:
                        break
                    start = max(offset, raw_position)
                    stop = min(end, block_end)
                    if start < stop:
                        output_files[current_node].write(
                            raw[start - raw_position : stop - raw_position]
                        )
                    if end <= block_end:
                        current_node += 1
                    else:
                        break
                raw_position = block_end
        finally:
            for output_file in output_files:
                output_file.close()
        for (_offset, size, path) in nodes:
            if (bundle_root / path).stat().st_size != size:
                raise ValueError(f"Output size mismatch: {path}")
        (bundle_root / ".complete").write_text(
            json.dumps({"source": source.name, "files": node_count}) + "\n"
        )
        return node_count, sum(size for _offset, size, _path in nodes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    sources = sorted(args.source.rglob("*.unity3d"))
    args.target.mkdir(parents=True, exist_ok=True)
    extracted = skipped = internal_files = total_bytes = 0
    failures = []
    for index, source in enumerate(sources, 1):
        destination = args.target / source.stem
        if (destination / ".complete").exists():
            skipped += 1
            continue
        try:
            count, size = extract_bundle(source, args.target)
            extracted += 1
            internal_files += count
            total_bytes += size
        except Exception as error:
            failures.append({"source": str(source), "error": str(error)})
            print(f"FAILED {source}: {error}", file=sys.stderr, flush=True)
        if index % 100 == 0 or index == len(sources):
            print(
                f"{index}/{len(sources)} bundles; extracted={extracted}, "
                f"skipped={skipped}, failed={len(failures)}",
                flush=True,
            )
    report = {
        "source_bundles": len(sources),
        "extracted_this_run": extracted,
        "skipped_completed": skipped,
        "internal_files_this_run": internal_files,
        "bytes_this_run": total_bytes,
        "failures": failures,
    }
    (args.target / "extraction_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
