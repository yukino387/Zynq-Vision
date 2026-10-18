import { createHash } from "node:crypto";
import { crc32 } from "node:zlib";
import type { FirmwareSegment } from "@vision/contracts";
import { DomainError } from "../core/errors.js";

/** 与 camera/firmware_layout.h 保持一致；任何一处改动都必须同步板端、FSBL 与打包脚本。 */
export const FIRMWARE_PACKAGE = {
  magic: 0x31474b50,
  format: 1,
  headerSize: 128,
  segmentSize: 16,
  maxSegments: 4,
  entry: 0x00100000,
  limit: 0x00200000,
  slotSize: 0x00400000,
  maxVersion: 56,
} as const;

export interface FirmwarePackage {
  version: string;
  sha256: string;
  size: number;
  imageSize: number;
  entry: number;
  payloadCrc32: number;
  segments: FirmwareSegment[];
}

function invalid(message: string): never {
  throw new DomainError("FIRMWARE_INCOMPATIBLE", message, 422);
}

export function validateFirmwarePackage(data: Buffer): FirmwarePackage {
  const { magic, format, headerSize, segmentSize, maxSegments, entry, limit } =
    FIRMWARE_PACKAGE;
  if (data.length < headerSize + segmentSize)
    invalid("Firmware package is too small");
  if (data.length > FIRMWARE_PACKAGE.slotSize)
    invalid("Firmware package exceeds the 4MiB slot");
  if (data.readUInt32LE(0) !== magic || data.readUInt32LE(4) !== format)
    invalid("Not a PKG1 firmware package");
  const declaredHeader = data.readUInt32LE(8);
  if (data.readUInt32LE(12) !== entry || data.readUInt32LE(16) !== entry)
    invalid("Firmware entry must be 0x00100000");
  const imageSize = data.readUInt32LE(20),
    count = data.readUInt32LE(24),
    versionLength = data.readUInt32LE(28),
    payloadCrc = data.readUInt32LE(32),
    headerCrc = data.readUInt32LE(36);
  if (count < 1 || count > maxSegments)
    invalid("Firmware package must contain 1..4 segments");
  const expectedHeader = headerSize + count * segmentSize;
  if (declaredHeader !== expectedHeader || data.length !== expectedHeader + imageSize)
    invalid("Firmware header or image size mismatch");
  if (imageSize === 0 || expectedHeader + imageSize > FIRMWARE_PACKAGE.slotSize)
    invalid("Firmware image size is invalid");
  if (versionLength < 1 || versionLength >= FIRMWARE_PACKAGE.maxVersion)
    invalid("Firmware version length is invalid");
  const versionBuffer = data.subarray(72, 128);
  if (versionBuffer[versionLength] !== 0)
    invalid("Firmware version is not NUL terminated");
  const version = versionBuffer.subarray(0, versionLength).toString("ascii");
  if (!version || /[^\x20-\x7e]/.test(version))
    invalid("Firmware version must be printable ASCII");

  // header_crc32 covers [0,36) + [40,128) + the segment table.
  const header = Buffer.concat([
    data.subarray(0, 36),
    data.subarray(40, 128),
    data.subarray(128, expectedHeader),
  ]);
  if (crc32(header) !== headerCrc) invalid("Firmware header CRC mismatch");

  const segments: FirmwareSegment[] = [];
  let payloadOffset = 0,
    previousEnd = 0;
  for (let index = 0; index < count; index++) {
    const at = 128 + index * 16;
    const paddr = data.readUInt32LE(at),
      offset = data.readUInt32LE(at + 4),
      size = data.readUInt32LE(at + 8);
    if (size === 0 || offset !== payloadOffset)
      invalid("Firmware segments must be contiguous");
    if (paddr < entry || paddr >= limit || size > limit - paddr)
      invalid("Firmware segment lies outside the application window");
    if (index && paddr < previousEnd)
      invalid("Firmware segments overlap or are out of order");
    previousEnd = paddr + size;
    payloadOffset += size;
    if (payloadOffset > imageSize)
      invalid("Firmware segment exceeds the image size");
    segments.push({ paddr, offset, size });
  }
  if (payloadOffset !== imageSize)
    invalid("Firmware segment table does not cover the image");

  const payload = data.subarray(expectedHeader);
  if (crc32(payload) !== payloadCrc)
    invalid("Firmware payload CRC mismatch");
  const sha256 = createHash("sha256").update(payload).digest("hex");
  if (sha256 !== data.subarray(40, 72).toString("hex"))
    invalid("Firmware payload SHA-256 mismatch");

  return {
    version,
    sha256,
    size: data.length,
    imageSize,
    entry,
    payloadCrc32: payloadCrc,
    segments,
  };
}
