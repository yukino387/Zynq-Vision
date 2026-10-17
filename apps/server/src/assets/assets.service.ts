import { Injectable } from "@nestjs/common";
import { mkdir, writeFile, readFile, statfs, unlink } from "node:fs/promises";
import { randomUUID, createHash } from "node:crypto";
import { resolve, dirname, sep } from "node:path";
import sharp from "sharp";
import { createWriteStream } from "node:fs";
import { Transform, type Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { Source } from "@vision/contracts";
import { config } from "../config.js";
import { DomainError } from "../core/errors.js";
@Injectable()
export class AssetsService {
  async exportStream(stream: Readable, fileName: string) {
    const storageKey = `exports/${randomUUID()}.zip`,
      path = this.path(storageKey);
    await mkdir(dirname(path), { recursive: true });
    const hash = createHash("sha256");
    let size = 0;
    let created = false;
    const target = createWriteStream(path, { flags: "wx" });
    target.once("open", () => {
      created = true;
    });
    try {
      await pipeline(
        stream,
        new Transform({
          transform(chunk: Buffer, _encoding, callback) {
            size += chunk.length;
            if (size > 1024 * 1024 * 1024)
              return callback(new Error("Export exceeds local 1GiB limit"));
            hash.update(chunk);
            callback(null, chunk);
          },
        }),
        target,
      );
    } catch (error) {
      if (created) await unlink(path).catch(() => undefined);
      throw error;
    }
    return {
      storageKey,
      fileName,
      mimeType: "application/zip",
      size,
      sha256: hash.digest("hex"),
    };
  }
  path(key: string) {
    const path = resolve(config.storage, key);
    if (!path.startsWith(config.storage + sep))
      throw new DomainError("ASSET_NOT_FOUND", "Invalid asset key", 404);
    return path;
  }
  async store(
    data: Buffer,
    kind: string,
    source: Source,
    originalName: string,
    mimeType: string,
    width?: number,
    height?: number,
  ) {
    const key = `${kind === "MODEL_ARTIFACT" ? "models" : "samples"}/${randomUUID()}`;
    const path = this.path(key);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, data, { flag: "wx" });
    return {
      storageKey: key,
      originalName,
      mimeType,
      size: data.length,
      sha256: createHash("sha256").update(data).digest("hex"),
      width: width ?? null,
      height: height ?? null,
      format: mimeType,
      kind,
      source,
    };
  }
  async read(key: string) {
    try {
      return await readFile(this.path(key));
    } catch {
      throw new DomainError("ASSET_NOT_FOUND", "Asset file is missing", 404);
    }
  }
  async preview(original: Buffer) {
    try {
      return await sharp(original, { limitInputPixels: 40000000 })
        .rotate()
        .jpeg({ quality: 85 })
        .toBuffer();
    } catch {
      throw new DomainError(
        "VALIDATION_ERROR",
        "Unsupported or corrupt image",
        400,
      );
    }
  }
  async quality(preview: Buffer) {
    const image = sharp(preview);
    const stats = await image.stats(),
      meta = await image.metadata();
    const { data, info } = await image
      .resize(128, 128, { fit: "inside" })
      .greyscale()
      .raw()
      .toBuffer({ resolveWithObject: true });
    let sum = 0,
      squares = 0,
      count = 0;
    for (let y = 1; y < info.height - 1; y++)
      for (let x = 1; x < info.width - 1; x++) {
        const i = y * info.width + x,
          v =
            4 * data[i]! -
            data[i - 1]! -
            data[i + 1]! -
            data[i - info.width]! -
            data[i + info.width]!;
        sum += v;
        squares += v * v;
        count++;
      }
    const sharpness = count ? squares / count - (sum / count) ** 2 : 0;
    const brightness =
      stats.channels.reduce((a, c) => a + c.mean, 0) / stats.channels.length;
    return {
      status:
        brightness < 30 || brightness > 230 || sharpness < 20
          ? "WARNING"
          : "PASS",
      metrics: {
        width: meta.width,
        height: meta.height,
        brightness,
        contrast:
          stats.channels.reduce((a, c) => a + c.stdev, 0) /
          stats.channels.length,
        sharpness,
        algorithm: "Laplacian variance at max 128px; advisory only",
      },
    };
  }
  async freeSpace() {
    await mkdir(config.storage, { recursive: true });
    const fs = await statfs(config.storage);
    return fs.bavail * fs.bsize;
  }
}
