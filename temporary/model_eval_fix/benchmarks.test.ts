import "reflect-metadata";
import { test } from "node:test";
import assert from "node:assert/strict";
import { BenchmarksController } from "../../apps/server/src/models/benchmarks.controller.js";
import type { Db } from "../../apps/server/src/core/db.js";
import type { ModelsService } from "../../apps/server/src/models/models.service.js";
import type { CommandsService } from "../../apps/server/src/devices/commands.service.js";
import { DomainError } from "../../apps/server/src/core/errors.js";

const digest = (byte: string) => byte.repeat(64);
const weights = (sha: string) => {
  const data = Buffer.alloc(128);
  Buffer.from(sha, "hex").copy(data, 88);
  return data;
};
function fixture(
  options: {
    sameVersion?: boolean;
    samePayload?: boolean;
    recovery?: boolean;
    fail?: boolean;
  } = {},
) {
  const originalVersion = options.sameVersion ? "candidate" : "original";
  const originalDigest = options.samePayload ? digest("b") : digest("a");
  const original = {
    model: { id: "original", version: originalVersion },
    manifest: {},
    weights: weights(originalDigest),
  };
  const candidate = {
    model: { id: "candidate", version: "candidate", manifest: {} },
    manifest: {},
    weights: weights(digest("b")),
  };
  const deployed: { version: string; sha256: string }[] = [];
  const commands: [string, number | undefined][] = [];
  const transport = {
    getStatus: () => ({
      runtimeState: "READY",
      reportedState: { cameraOnly: true, modelPayloadSha256: originalDigest },
    }),
    getCurrentModel: () => originalVersion,
    deployModel: async (version: string, _manifest: unknown, data: Buffer) => {
      deployed.push({
        version,
        sha256: data.subarray(88, 120).toString("hex"),
      });
      if (options.fail && deployed.length === 1)
        throw new Error("candidate activation failed");
    },
    sendCommand: async (type: string, value?: number) => {
      commands.push([type, value]);
    },
    captureOnce: async () => ({
      frameId: 42,
      modelState: {
        modelVersion: "candidate",
        modelPayloadSha256: digest("b"),
      },
      outputs: { out0: Buffer.alloc(1), out1: Buffer.alloc(1) },
      telemetry: {
        errorCode: 0,
        inferenceUs: 60000,
        cycleUs: 65000,
        fps: 15.38,
      },
    }),
  };
  const db = {
    dataset: { findUniqueOrThrow: async () => ({ status: "FROZEN" }) },
    device: { findUniqueOrThrow: async () => ({ type: "ZYNQ" }) },
    model: { findMany: async () => (options.recovery ? [original.model] : []) },
    benchmark: { create: async ({ data }: { data: unknown }) => data },
    $transaction: async (action: (tx: unknown) => Promise<unknown>) =>
      action(db),
  };
  const controller = new BenchmarksController(
    db as unknown as Db,
    {
      check: async () => ({ ...candidate, transport }),
      artifact: async () => original,
    } as unknown as ModelsService,
    {
      run: async (
        _id: string,
        _type: string,
        _request: string,
        action: () => Promise<unknown>,
      ) => action(),
    } as unknown as CommandsService,
  );
  return { controller, deployed, commands, originalVersion, originalDigest };
}
const dto = {
  name: "Regression evaluation",
  modelId: "candidate",
  datasetId: "frozen",
  deviceId: "board",
};
for (const sameVersion of [false, true]) {
  test(`missing exact recovery blocks deployment (same version: ${sameVersion})`, async () => {
    const f = fixture({ sameVersion });
    await assert.rejects(f.controller.create(dto), (error: unknown) => {
      assert.ok(error instanceof DomainError);
      assert.equal(error.getStatus(), 409);
      assert.equal(
        (error.getResponse() as { code: string }).code,
        "MODEL_RESTORE_REQUIRED",
      );
      return true;
    });
    assert.deepEqual(f.deployed, []);
  });
}
test("same version with different payload restores the exact original and run mode", async () => {
  const f = fixture({ sameVersion: true, recovery: true });
  const result = (await f.controller.create(dto)) as unknown as {
    metrics: { candidateExecuted: boolean; restoredModelPayloadSha256: string };
  };
  assert.equal(result.metrics.candidateExecuted, true);
  assert.equal(result.metrics.restoredModelPayloadSha256, f.originalDigest);
  assert.deepEqual(f.deployed, [
    { version: "candidate", sha256: digest("b") },
    { version: f.originalVersion, sha256: f.originalDigest },
  ]);
  assert.deepEqual(f.commands.slice(-2), [
    ["CAMERA_ONLY", 1],
    ["STOP_INSPECTION", undefined],
  ]);
});
test("candidate activation failure still restores original weights and mode", async () => {
  const f = fixture({ recovery: true, fail: true });
  await assert.rejects(f.controller.create(dto), /candidate activation failed/);
  assert.equal(f.deployed[1]?.sha256, f.originalDigest);
  assert.deepEqual(f.commands.slice(-2), [
    ["CAMERA_ONLY", 1],
    ["STOP_INSPECTION", undefined],
  ]);
});
test("the exact active version and payload need no separate recovery artifact", async () => {
  const f = fixture({ sameVersion: true, samePayload: true });
  await f.controller.create(dto);
  assert.equal(f.deployed.length, 1);
});
