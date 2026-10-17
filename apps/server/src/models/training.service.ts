import { Injectable, Inject } from "@nestjs/common";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import { Prisma } from "@prisma/client";
import { manifestSchema, trainingOptionsSchema } from "@vision/contracts";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { AssetsService } from "../assets/assets.service.js";
import { config, root } from "../config.js";
import { validateZynqPackage } from "./zynq-profile.js";

@Injectable()
export class TrainingService {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(Events) private events: Events,
    @Inject(AssetsService) private assets: AssetsService,
  ) {}

  async run(id: string, payload: Prisma.JsonValue, stopping: () => boolean) {
    const options = trainingOptionsSchema.parse(
      (payload as Prisma.JsonObject)?.options ?? {},
    );
    const training = await this.db.trainingJob.findUniqueOrThrow({
      where: { id },
      include: {
        dataset: {
          include: {
            items: {
              orderBy: { sampleId: "asc" },
              include: { sample: { include: { assets: true } } },
            },
          },
        },
      },
    });
    if (training.status === "CANCELLED") return;
    const dataset = training.dataset;
    if (dataset.status !== "FROZEN" || !dataset.items.length)
      throw new Error("Training requires a nonempty frozen dataset");
    const checksum = createHash("sha256")
      .update(
        JSON.stringify(
          dataset.items.map((i) => ({
            sampleId: i.sampleId,
            annotationSetId: i.annotationSetId,
            split: i.split,
            snapshot: i.snapshot,
          })),
        ),
      )
      .digest("hex");
    if (checksum !== dataset.checksum)
      throw new Error("Frozen dataset checksum mismatch");
    const items = [];
    let classes: string[] | undefined;
    let hasUnscopedItems = false;
    for (const item of dataset.items) {
      const snapshot = item.snapshot as {
        width: number;
        height: number;
        previewId: string;
        sha256: string;
        assets: { id: string; kind: string; sha256: string }[];
        boxes: Prisma.JsonValue[];
        classes?: string[];
      };
      if (snapshot.classes?.length) {
        if (snapshot.classes.length > 6)
          throw new Error("当前模板最多支持六类对象");
        if (
          classes &&
          JSON.stringify(classes) !== JSON.stringify(snapshot.classes)
        )
          throw new Error(
            "同一训练版本不能混用不同方案的类别，请分别整理数据集",
          );
        classes = snapshot.classes;
      } else hasUnscopedItems = true;
      const raw = snapshot.assets.find(
        (a) =>
          a.kind === "RAW" &&
          item.sample.assets.some(
            (s) => s.id === a.id && s.format === "RGB565_LE",
          ),
      );
      const chosen =
        raw ??
        snapshot.assets.find(
          (a) => a.id === snapshot.previewId && a.sha256 === snapshot.sha256,
        );
      const asset = item.sample.assets.find(
        (a) => a.id === chosen?.id && a.sha256 === chosen.sha256,
      );
      if (!asset)
        throw new Error("Frozen dataset image is missing or was modified");
      if (
        createHash("sha256")
          .update(await this.assets.read(asset.storageKey))
          .digest("hex") !== asset.sha256
      )
        throw new Error("Frozen dataset asset checksum mismatch");
      items.push({
        id: item.sampleId,
        path: this.assets.path(asset.storageKey),
        sha256: asset.sha256,
        raw: Boolean(raw),
        width: snapshot.width,
        height: snapshot.height,
        split: item.split,
        boxes: snapshot.boxes,
      });
    }
    const directory = resolve(config.storage, "training", id);
    if (classes && hasUnscopedItems)
      throw new Error("请勿将未关联方案的历史样本与方案样本混入同一训练版本");
    const version = `INT8-${id}`;
    await mkdir(directory, { recursive: true });
    const spec = resolve(directory, "spec.json");
    await writeFile(
      spec,
      JSON.stringify({
        options,
        items,
        version,
        classes: classes
          ? [
              ...classes,
              ...Array.from(
                { length: 6 - classes.length },
                (_, i) => `_unused_${classes.length + i}`,
              ),
            ]
          : undefined,
        datasetChecksum: checksum,
      }),
    );
    const claim = await this.db.trainingJob.updateMany({
      where: { id, status: "QUEUED" },
      data: { status: "RUNNING", stage: "Preparing Dataset", progress: 1 },
    });
    if (!claim.count) return;
    let stderr = "",
      cancelled = false,
      stopError: Error | null = null;
    const child = spawn(
      config.TRAINING_PYTHON,
      [
        "-u",
        resolve(root, "camera/training/train.py"),
        "--spec",
        spec,
        "--output",
        directory,
      ],
      {
        cwd: root,
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, PYTHONUTF8: "1" },
      },
    );
    child.stderr.on("data", (data: Buffer) => {
      stderr = (stderr + data.toString("utf8")).slice(-6000);
    });
    const lines = createInterface({ input: child.stdout });
    let updates = Promise.resolve();
    lines.on("line", (line) => {
      updates = updates
        .then(async () => {
          const event = JSON.parse(line) as {
            stage: string;
            progress: number;
            epoch?: number;
            loss?: number;
          };
          if (
            !Number.isInteger(event.progress) ||
            event.progress < 0 ||
            event.progress > 99 ||
            typeof event.stage !== "string"
          )
            throw new Error("Invalid training progress");
          const updated = await this.db.trainingJob.updateMany({
            where: { id, status: "RUNNING" },
            data: { stage: event.stage, progress: event.progress },
          });
          if (updated.count) this.events.emit("training.progress", id, event);
        })
        .catch((error) => {
          stopError = error instanceof Error ? error : new Error(String(error));
          child.kill();
        });
    });
    let checking = false;
    const timer = setInterval(() => {
      if (checking) return;
      checking = true;
      void this.db.trainingJob
        .findUniqueOrThrow({ where: { id } })
        .then((current) => {
          cancelled = current.status === "CANCELLED";
          if (cancelled || stopping()) child.kill();
        })
        .catch((error) => {
          stopError = error;
          child.kill();
        })
        .finally(() => {
          checking = false;
        });
    }, 300);
    try {
      const code = await new Promise<number | null>((accept, reject) => {
        child.once("error", reject);
        child.once("close", accept);
      });
      await updates;
      const latest = await this.db.trainingJob.findUniqueOrThrow({
        where: { id },
      });
      if (cancelled || latest.status === "CANCELLED") return;
      if (stopError) throw stopError;
      if (code !== 0)
        throw new Error(
          `Training process failed (${code}): ${stderr || "Python/PyTorch runtime unavailable"}`,
        );
      if (stopping()) throw new Error("Server shutdown during training");
      const manifest = manifestSchema.parse(
        JSON.parse(await readFile(resolve(directory, "manifest.json"), "utf8")),
      );
      const weights = await readFile(resolve(directory, "model.bin"));
      validateZynqPackage(weights, version, manifest);
      const report = JSON.parse(
        await readFile(resolve(directory, "report.json"), "utf8"),
      ) as { metrics: Prisma.InputJsonValue };
      const artifacts: Prisma.ModelArtifactCreateWithoutModelInput[] = [];
      for (const [kind, file, mime] of [
        ["WEIGHTS", "model.bin", "application/octet-stream"],
        ["PL_WEIGHTS", "weights.bin", "application/octet-stream"],
        ["PL_METADATA", "metadata.bin", "application/octet-stream"],
        ["CHECKPOINT", "checkpoint.pt", "application/octet-stream"],
        ["TRAINING_REPORT", "report.json", "application/json"],
        ["QUANTIZATION", "quantization.json", "application/json"],
      ]) {
        const asset = await this.assets.store(
          await readFile(resolve(directory, file!)),
          "MODEL_ARTIFACT",
          "IMPORT",
          kind!.startsWith("PL_") ? `pl/${file}` : file!,
          mime!,
        );
        artifacts.push({ kind: kind!, asset: { create: asset } });
      }
      const completed = await this.db.$transaction(async (tx) => {
        const changed = await tx.trainingJob.updateMany({
          where: { id, status: "RUNNING" },
          data: { status: "COMPLETED", stage: "Completed", progress: 100 },
        });
        if (!changed.count) return false;
        await tx.model.create({
          data: {
            name: training.name,
            version,
            architecture: manifest.networkTemplate,
            trainingId: id,
            source: "IMPORT",
            manifest: manifest as unknown as Prisma.InputJsonValue,
            metrics: report.metrics,
            artifacts: { create: artifacts },
          },
        });
        return true;
      });
      if (completed) this.events.emit("training.completed", id, { version });
    } finally {
      clearInterval(timer);
      lines.close();
    }
  }
}
