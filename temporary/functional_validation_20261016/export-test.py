from pathlib import Path
p=Path('temporary/iot_platform_test/platform.test.ts');s=p.read_text(encoding='utf-8')
s=s.replace('import { test, before, after } from "node:test";','import { test, before, after } from "node:test";\nimport { inflateRawSync } from "node:zlib";')
needle='const output = resolve("temporary/iot_platform_test", `run-${Date.now()}`);'
helper='''// Inspect archive entries rather than accepting a ZIP signature as a usable export.
function unzip(data: Buffer) {
  const end = data.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  assert.ok(end >= 0, "ZIP must have a central directory");
  const count = data.readUInt16LE(end + 10);
  let cursor = data.readUInt32LE(end + 16);
  const files = new Map<string, Buffer>();
  for (let i = 0; i < count; i++) {
    assert.equal(data.readUInt32LE(cursor), 0x02014b50);
    const method = data.readUInt16LE(cursor + 10);
    const compressedSize = data.readUInt32LE(cursor + 20);
    const nameLength = data.readUInt16LE(cursor + 28);
    const extraLength = data.readUInt16LE(cursor + 30);
    const commentLength = data.readUInt16LE(cursor + 32);
    const offset = data.readUInt32LE(cursor + 42);
    const name = data.subarray(cursor + 46, cursor + 46 + nameLength).toString();
    assert.equal(data.readUInt32LE(offset), 0x04034b50);
    const start = offset + 30 + data.readUInt16LE(offset + 26) + data.readUInt16LE(offset + 28);
    const compressed = data.subarray(start, start + compressedSize);
    assert.ok(method === 0 || method === 8);
    files.set(name, method === 8 ? inflateRawSync(compressed) : compressed);
    cursor += 46 + nameLength + extraLength + commentLength;
  }
  return files;
}
'''
s=s.replace(needle,helper+needle)
needle='  assert.equal(zip.rawPayload.subarray(0, 2).toString(), "PK");'
s=s.replace(needle,needle+'''
  const files = unzip(zip.rawPayload);
  const imageName = `images/${sample.id}.jpg`, labelName = `labels/${sample.id}.txt`;
  assert.ok(files.has(imageName), "YOLO image must share its basename with the label");
  const image = files.get(imageName)!;
  const imageMeta = await sharp(image).metadata();
  assert.equal(imageMeta.width, 416);
  assert.equal(imageMeta.height, 416);
  assert.deepEqual(files.get(labelName)!.toString().split(" ").map(Number), [
    5, 115 / 416, 200 / 416, 70 / 416, 240 / 416,
  ]);
  const original = sample.assets.find((a) => a.kind === "RAW")!;
  const rawPath = `originals/${sample.id}/${original.id}.raw`;
  const originalResponse = await app.inject({ method: "GET", url: `/api/assets/${original.id}/content`, headers: { authorization: `Bearer ${engineer}` } });
  assert.deepEqual(files.get(rawPath), originalResponse.rawPayload);
  const modelExport = await app.inject({ method: "POST", url: `/api/models/${model.id}/export`, headers: { authorization: `Bearer ${engineer}` } });
  assert.equal(modelExport.statusCode, 201);
  const modelFiles = unzip(modelExport.rawPayload);
  const modelManifest = JSON.parse(modelFiles.get("manifest.json")!.toString());
  const weights = modelFiles.get("weights.simulated")!;
  assert.equal(createHash("sha256").update(weights).digest("hex"), modelManifest.weights.sha256);
  assert.equal(weights.length, modelManifest.weights.size);
''')
p.write_text(s,encoding='utf-8')
