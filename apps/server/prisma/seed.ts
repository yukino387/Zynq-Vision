import "reflect-metadata";
import { PrismaClient, Prisma } from "@prisma/client";
import { hash } from "bcryptjs";
import { createHash } from "node:crypto";
import sharp from "sharp";
import { AssetsService } from "../src/assets/assets.service.js";
import { simulatorManifest, simulatedWeights } from "../src/models/profile.js";
import { SimulatorTransport } from "../src/devices/simulator.js";
import { baseCapabilities } from "../src/devices/transport.js";
import "../src/config.js";
const db = new PrismaClient();
try {
  const password = process.env.SEED_PASSWORD;
  if (!password || password.length < 12)
    throw new Error("Set SEED_PASSWORD (minimum 12 characters) in .env");
  const passwordHash = await hash(password, 12);
  for (const role of ["ADMIN", "ENGINEER", "OPERATOR"] as const)
    await db.user.upsert({
      where: { username: role.toLowerCase() },
      update: {},
      create: {
        username: role.toLowerCase(),
        name: `${role} / DEMO`,
        role,
        passwordHash,
      },
    });
  const station = await db.station.upsert({
    where: { code: "DEMO-LAB-01" },
    update: {},
    create: { code: "DEMO-LAB-01", name: "DEMO · 视觉实验工位" },
  });
  const device = await db.device.upsert({
    where: { serialNumber: "SIMULATED-001" },
    update: {},
    create: {
      name: "SIMULATED · Lab Device 01",
      serialNumber: "SIMULATED-001",
      type: "SIMULATOR",
      stationId: station.id,
      protocolVersion: "SIMULATED-v1",
      capabilities: {
        ...baseCapabilities,
        modelUpdate: true,
        firmwareUpdate: true,
        modelVersion: true,
        planUpdate: true,
      },
      desiredState: {
        modelVersion: "SIM-V1",
        planVersion: "SIM-P1",
        inspectionEnabled: true,
      },
      reportedState: {
        modelVersion: "SIM-V1",
        planVersion: "SIM-P1",
        inspectionEnabled: true,
      },
    },
  });
  await db.device.upsert({
    where: { serialNumber: "ZYNQ-SOURCE-CONFIGURED" },
    update: {},
    create: {
      name: "Zynq-7020 · 配置端点",
      serialNumber: "ZYNQ-SOURCE-CONFIGURED",
      type: "ZYNQ",
      stationId: station.id,
      ipAddress: process.env.ZYNQ_HOST ?? "169.254.140.110",
      protocolVersion: "CNC1/CST1/YLO1 (source verified)",
      capabilities: baseCapabilities as unknown as Prisma.InputJsonValue,
      metadata: {
        identity: "Not reported by firmware; registered endpoint only",
      },
    },
  });
  const plan = await db.inspectionPlan.upsert({
    where: { name_version: { name: "SIMULATED defect review", version: 1 } },
    update: {},
    create: {
      name: "SIMULATED defect review",
      version: 1,
      rules: {
        source: "SIMULATION",
        defectThreshold: 0.7,
        emptyResult: "REVIEW",
      },
    },
  });
  let task = await db.task.findFirst({
    where: { name: "DEMO · 表面缺陷采集" },
  });
  if (!task)
    task = await db.task.create({
      data: {
        name: "DEMO · 表面缺陷采集",
        target: 30,
        stationId: station.id,
        planId: plan.id,
      },
    });
  const assets = new AssetsService();
  if (
    !(await db.model.findUnique({
      where: {
        name_version: { name: "SIMULATED defect model", version: "SIM-V1" },
      },
    }))
  ) {
    const weights = simulatedWeights("SIM-V1"),
      manifest = simulatorManifest(weights),
      asset = await assets.store(
        weights,
        "MODEL_ARTIFACT",
        "SIMULATION",
        "SIM-V1.simulated",
        "application/octet-stream",
      );
    const model = await db.model.create({
      data: {
        name: "SIMULATED defect model",
        version: "SIM-V1",
        architecture: "SIMULATOR_DEFECT_V1",
        source: "SIMULATION",
        status: "APPROVED",
        manifest: manifest as unknown as Prisma.InputJsonValue,
        artifacts: { create: { kind: "WEIGHTS", asset: { create: asset } } },
      },
    });
    const simulator = new SimulatorTransport();
    await simulator.connect();
    const receipt = await simulator.deployModel(
      model.version,
      manifest,
      weights,
      async () => {},
    );
    await simulator.disconnect();
    await db.deployment.create({
      data: {
        name: "SIMULATED · initial fixture deployment",
        deviceId: device.id,
        modelId: model.id,
        status: "ACTIVE",
        source: "SIMULATION",
        progress: 100,
        receipt: receipt as unknown as Prisma.InputJsonValue,
      },
    });
  }
  const admin = await db.user.findUniqueOrThrow({
    where: { username: "admin" },
  });
  for (let index = 0; index < 3; index++) {
    const key = `demo-sample-${index}`;
    if (await db.sample.findUnique({ where: { idempotencyKey: key } }))
      continue;
    const svg = Buffer.from(
      `<svg width="416" height="416"><rect width="416" height="416" fill="#a4aaa0"/><path d="M110 100 L120 170 L108 240 L118 290" stroke="#38483b" stroke-width="6" fill="none"/><text x="20" y="35" fill="#163c28" font-size="18">SIMULATED · DEMO ${index + 1}</text></svg>`,
    );
    const jpeg = await sharp(svg).jpeg().toBuffer();
    const raw = await assets.store(
        svg,
        "RAW",
        "SIMULATION",
        "simulated.svg",
        "image/svg+xml",
        416,
        416,
      ),
      preview = await assets.store(
        jpeg,
        "PREVIEW",
        "SIMULATION",
        "demo.jpg",
        "image/jpeg",
        416,
        416,
      );
    const box = {
      classId: 5,
      label: "划痕",
      confidence: 0.82,
      x1: 90,
      y1: 80,
      x2: 145,
      y2: 310,
    };
    const sample = await db.sample.create({
      data: {
        name: `SIMULATED · Demo sample ${index + 1}`,
        source: "SIMULATION",
        clientId: "demo-seed",
        localSequence: index,
        idempotencyKey: key,
        taskId: task.id,
        capturedAt: new Date(),
        metadata: { uploadedBy: admin.id, label: "SIMULATED" },
        assets: { create: [raw, preview] },
        quality: { create: await assets.quality(jpeg) },
        annotations: {
          create: {
            userId: admin.id,
            version: 1,
            status: "COMPLETE",
            boxes: { create: box },
          },
        },
      },
    });
    const model = await db.model.findFirstOrThrow({
      where: { version: "SIM-V1" },
    });
    await db.inspection.create({
      data: {
        sampleId: sample.id,
        deviceId: device.id,
        stationId: station.id,
        taskId: task.id,
        modelId: model.id,
        modelVersion: model.version,
        source: "SIMULATION",
        startedAt: new Date(),
        completedAt: new Date(),
        result: index === 0 ? "FAIL" : index === 1 ? "REVIEW" : "PASS",
        reason: "SIMULATED seed fixture; no hardware observation",
        confidence: index === 2 ? null : 0.82,
        detections: index === 2 ? undefined : { create: box },
      },
    });
  }
  if (
    !(await db.dataset.findUnique({
      where: { name_version: { name: "DEMO · Surface defects", version: 1 } },
    }))
  ) {
    const samples = await db.sample.findMany({
      where: { clientId: "demo-seed" },
      include: { assets: true, annotations: { include: { boxes: true } } },
    });
    const items = samples.map((s) => {
      const preview = s.assets.find((a) => a.kind === "PREVIEW")!;
      return {
        sampleId: s.id,
        annotationSetId: s.annotations[0]!.id,
        snapshot: {
          source: "SIMULATION",
          width: 416,
          height: 416,
          previewId: preview.id,
          sha256: preview.sha256,
          boxes: s.annotations[0]!.boxes,
        } as unknown as Prisma.InputJsonValue,
      };
    });
    await db.dataset.create({
      data: {
        name: "DEMO · Surface defects",
        version: 1,
        status: "FROZEN",
        checksum: createHash("sha256")
          .update(JSON.stringify(items))
          .digest("hex"),
        frozenAt: new Date(),
        items: { create: items },
      },
    });
  }
  console.log(
    "Seed ready: admin, engineer, operator. DEMO and SIMULATED data only; credentials remain in local .env.",
  );
} finally {
  await db.$disconnect();
}
