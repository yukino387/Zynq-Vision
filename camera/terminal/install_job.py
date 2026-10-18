#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import uuid
import zipfile
import zlib


def durable(path, content):
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o600)


def install(package, state):
    with zipfile.ZipFile(package) as archive:
        if sorted(archive.namelist()) != ["job.json", "model.bin"]:
            raise ValueError("The job archive must contain only job.json and model.bin")
        if archive.getinfo("job.json").file_size > 1024 * 1024 or archive.getinfo("model.bin").file_size != 6416360:
            raise ValueError("Unexpected job package size")
        descriptor, model = archive.read("job.json"), archive.read("model.bin")
    job = json.loads(descriptor)
    if job.get("formatVersion") != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", job["id"]):
        raise ValueError("Invalid job identity")
    if hashlib.sha256(model).hexdigest() != job["modelSha256"] or job["modelSha256"] != job["manifest"]["weights"]["sha256"]:
        raise ValueError("Model file checksum mismatch")
    if struct.unpack_from("<IIII", model) != (0x314E4E43, 1, 6350208, 66024):
        raise ValueError("Invalid model header")
    if zlib.crc32(model[:120]) != struct.unpack_from("<I", model, 120)[0]:
        raise ValueError("Model header checksum mismatch")
    if hashlib.sha256(model[128:]).hexdigest() != job["snapshot"]["modelPayloadSha256"] or model[88:120].hex() != job["snapshot"]["modelPayloadSha256"]:
        raise ValueError("Model payload checksum mismatch")
    if model[24:88].split(b"\0", 1)[0].decode("ascii") != job["snapshot"]["modelVersion"]:
        raise ValueError("Model version mismatch")
    root = state / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / job["id"]
    if destination.exists():
        if (destination / "job.json").read_bytes() == descriptor and hashlib.sha256((destination / "model.bin").read_bytes()).hexdigest() == job["modelSha256"]:
            return destination
        raise ValueError("A different package already uses this immutable job ID")
    staging = root / (".install-" + str(uuid.uuid4()))
    staging.mkdir(mode=0o700)
    durable(staging / "job.json", descriptor)
    durable(staging / "model.bin", model)
    if os.name != "nt":
        directory = os.open(staging, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    staging.rename(destination)
    if os.name != "nt":
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--state", type=Path, default=Path("/var/lib/vision"))
    args = parser.parse_args()
    print(install(args.package, args.state))
