"""Build the PS application OTA package from camera_live.elf.

The on-board FSBL only understands the package format in camera/firmware_layout.h:
a 128-byte header, a segment table and the concatenated ELF PT_LOAD payload.
No external dependencies; parsing is done directly from the ELF32 program headers.
"""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

MAGIC = 0x31474B50  # "PKG1"
FORMAT = 1
APP_ENTRY = 0x00100000
APP_LIMIT = 0x00200000
MAX_SEGMENTS = 4
MAX_VERSION = 56
MAX_PACKAGE = 0x00400000
PT_LOAD = 1


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def load_segments(elf: bytes):
    if len(elf) < 52 or elf[:4] != b"\x7fELF":
        raise ValueError("Not an ELF file")
    if elf[4] != 1 or elf[5] != 1:
        raise ValueError("Only 32-bit little-endian ARM ELF is supported")
    entry = struct.unpack_from("<I", elf, 24)[0]
    phoff = struct.unpack_from("<I", elf, 28)[0]
    phentsize = struct.unpack_from("<H", elf, 42)[0]
    phnum = struct.unpack_from("<H", elf, 44)[0]
    if phentsize < 32 or phoff + phentsize * phnum > len(elf):
        raise ValueError("Invalid program header table")
    segments = []
    for index in range(phnum):
        offset = phoff + index * phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = (
            struct.unpack_from("<8I", elf, offset)
        )
        if p_type != PT_LOAD or p_filesz == 0:
            continue
        paddr = p_paddr or p_vaddr
        if p_offset + p_filesz > len(elf):
            raise ValueError(f"Segment {index} exceeds ELF file")
        segments.append(
            {
                "paddr": paddr,
                "offset": p_offset,
                "size": p_filesz,
                "memsz": p_memsz,
                "flags": p_flags,
            }
        )
    segments.sort(key=lambda item: item["paddr"])
    if not segments:
        raise ValueError("ELF has no loadable segments")
    if entry != APP_ENTRY:
        raise ValueError(f"ELF entry {entry:#x} must be {APP_ENTRY:#x}")
    if segments[0]["paddr"] != APP_ENTRY:
        raise ValueError(f"First segment {segments[0]['paddr']:#x} must be {APP_ENTRY:#x}")
    if len(segments) > MAX_SEGMENTS:
        raise ValueError(f"Too many loadable segments: {len(segments)}")
    previous_end = 0
    payload_size = 0
    for segment in segments:
        start, end = segment["paddr"], segment["paddr"] + segment["size"]
        if start < APP_ENTRY or end > APP_LIMIT:
            raise ValueError(f"Segment {start:#x}..{end:#x} outside app window")
        if start < previous_end:
            raise ValueError("Segments overlap or are not sorted")
        previous_end = end
        payload_size += segment["size"]
    if payload_size > MAX_PACKAGE:
        raise ValueError(f"Payload too large: {payload_size} bytes")
    payload_offset = 0
    for segment in segments:
        segment["payload_offset"] = payload_offset
        payload_offset += segment["size"]
    return entry, segments


def build(elf_path: Path, version: str, skip_version_check: bool):
    elf = elf_path.read_bytes()
    encoded_version = version.encode("ascii")
    if not 1 <= len(encoded_version) <= MAX_VERSION - 1 or b"\0" in encoded_version:
        raise ValueError(f"Version must be 1..{MAX_VERSION - 1} ASCII bytes without NUL")
    if not skip_version_check and encoded_version not in elf:
        raise ValueError(
            "Version string is not present in the ELF; rebuild the app with "
            "camera/build/firmware/firmware_version.h or pass --skip-version-check"
        )
    entry, segments = load_segments(elf)
    payload = b"".join(
        elf[item["offset"] : item["offset"] + item["size"]] for item in segments
    )
    image_size = len(payload)
    payload_crc = crc32(payload)
    payload_sha = hashlib.sha256(payload).digest()
    segment_table = b"".join(
        struct.pack("<4I", item["paddr"], item["payload_offset"], item["size"], 0)
        for item in segments
    )
    header_size = 128 + len(segments) * 16
    header = struct.pack(
        "<10I",
        MAGIC,
        FORMAT,
        header_size,
        entry,
        APP_ENTRY,
        image_size,
        len(segments),
        len(encoded_version),
        payload_crc,
        0,
    ) + payload_sha + encoded_version.ljust(MAX_VERSION, b"\0")
    if len(header) != 128:
        raise AssertionError("Header must be 128 bytes")
    header_crc = crc32(header[:36] + header[40:128] + segment_table)
    header = header[:36] + struct.pack("<I", header_crc) + header[40:]
    package = header + segment_table + payload
    if len(package) > MAX_PACKAGE:
        raise ValueError(f"Package too large: {len(package)} bytes")
    return {
        "package": package,
        "version": version,
        "entry": entry,
        "image_size": image_size,
        "segment_count": len(segments),
        "segments": [
            {
                "paddr": item["paddr"],
                "offset": item["payload_offset"],
                "file_offset": item["offset"],
                "size": item["size"],
            }
            for item in segments
        ],
        "payload_crc32": f"{payload_crc:08x}",
        "payload_sha256": payload_sha.hex(),
        "header_crc32": f"{header_crc:08x}",
        "sha256": hashlib.sha256(package).hexdigest(),
        "size": len(package),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-version-check", action="store_true")
    args = parser.parse_args()
    result = build(args.elf, args.version, args.skip_version_check)
    args.output.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in args.version)
    package_path = args.output / f"{args.elf.stem}-{safe}.fw"
    package_path.write_bytes(result.pop("package"))
    (args.output / f"{args.elf.stem}-{safe}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
