// 模型与发布界面的本地假数据：仅用于截图核对显示效果，不参与正式链路。
import { createServer } from "node:http";
import { pathToFileURL } from "node:url";

const page = (items) => ({ items, total: items.length, page: 1, pageSize: 20 });

const models = [
  {
    id: "mdl_9f31ac2b7e",
    name: "表面划痕检测 v4",
    version: "V4.2.1",
    status: "APPROVED",
    source: "REAL",
    trainingId: "trn_77ac1",
    createdAt: "2026-10-15T09:24:11.000Z",
    metrics: { mAP50: 0.912, precision: 0.94, recall: 0.887, fps: 16.5, inferenceUs: 60400 },
    benchmarks: [{ id: "b1" }, { id: "b2" }],
    manifest: { inputChannels: 1, quantization: "INT8" },
  },
  {
    id: "mdl_4c02de88a1",
    name: "表面划痕检测 v3",
    version: "V3.8.0",
    status: "ACTIVE",
    source: "REAL",
    trainingId: "trn_52bd0",
    createdAt: "2026-10-11T14:02:55.000Z",
    metrics: { mAP50: 0.874, precision: 0.902, recall: 0.851, fps: 16.4 },
    benchmarks: [{ id: "b3" }],
    manifest: { inputChannels: 1, quantization: "INT8" },
  },
  {
    id: "mdl_1a77ff30cd",
    name: "药片缺角检测",
    version: "V1.0.3",
    status: "CANDIDATE",
    source: "SIMULATION",
    createdAt: "2026-10-14T20:41:03.000Z",
    metrics: {},
    benchmarks: [],
    manifest: {},
  },
  {
    id: "mdl_02bb9c14ee",
    name: "纺织断经检测",
    version: "V2.1.0",
    status: "CANDIDATE",
    source: "REAL",
    trainingId: "trn_31fe2",
    createdAt: "2026-10-09T08:15:44.000Z",
    metrics: { mAP50: 0.803, precision: 0.821, recall: 0.79, fps: 15.2 },
    benchmarks: [{ id: "b4" }],
    manifest: {},
  },
];

const trainings = [
  {
    id: "trn_8891aa02c1",
    name: "划痕数据集 v4 训练",
    status: "RUNNING",
    stage: "TRAIN",
    progress: 62,
    source: "REAL",
    createdAt: "2026-10-17T20:04:12.000Z",
    error: null,
    options: { colorMode: "GRAY", epochs: 100, batchSize: 16, learningRate: 0.001, seed: 7020, device: "cuda", amp: true, workers: 4 },
    models: [],
  },
  {
    id: "trn_7710bb15d2",
    name: "药片缺角 快速验证",
    status: "QUEUED",
    stage: "QUEUE",
    progress: 0,
    source: "REAL",
    createdAt: "2026-10-17T19:52:40.000Z",
    error: null,
    options: { colorMode: "GRAY", epochs: 5, batchSize: 32, learningRate: 0.001, seed: 7020, device: "cuda", amp: true, workers: 4 },
    models: [],
  },
  {
    id: "trn_3102fe9a44",
    name: "划痕数据集 v4 训练",
    status: "COMPLETED",
    stage: "DONE",
    progress: 100,
    source: "REAL",
    createdAt: "2026-10-15T07:11:09.000Z",
    error: null,
    options: { colorMode: "GRAY", epochs: 100, batchSize: 16, learningRate: 0.001, seed: 7020, device: "cuda", amp: true, workers: 4 },
    models: [{ id: "mdl_9f31ac2b7e", version: "V4.2.1" }],
  },
  {
    id: "trn_2204cd7710",
    name: "纺织断经 基线训练",
    status: "FAILED",
    stage: "VALIDATE",
    progress: 38,
    source: "REAL",
    createdAt: "2026-10-12T11:31:00.000Z",
    error: "验证集样本不足：需要至少 20 张已标注样本，当前 6 张。",
    options: { colorMode: "RGB", epochs: 50, batchSize: 32, learningRate: 0.001, seed: 7020, device: "cuda", amp: false, workers: 2 },
    models: [],
  },
  {
    id: "trn_1190ab33ff",
    name: "模拟样本流程验证",
    status: "COMPLETED",
    stage: "DONE",
    progress: 100,
    source: "SIMULATION",
    createdAt: "2026-10-08T16:02:21.000Z",
    error: null,
    models: [],
  },
];

const benchmarks = [
  {
    id: "bmk_71aa02cd33",
    name: "划痕 v4 板端对照",
    status: "COMPLETED",
    stage: "DONE",
    progress: 100,
    source: "REAL",
    createdAt: "2026-10-16T10:22:41.000Z",
    metrics: { fps: 16.5, inferenceUs: 60400, mAP50: 0.912 },
    model: models[0],
  },
  {
    id: "bmk_33cd7710aa",
    name: "划痕 v3 板端对照",
    status: "COMPLETED",
    stage: "DONE",
    progress: 100,
    source: "REAL",
    createdAt: "2026-10-12T09:47:12.000Z",
    metrics: { fps: 16.4, inferenceUs: 60800, mAP50: 0.874 },
    model: models[1],
  },
  {
    id: "bmk_09fe2211bb",
    name: "纺织断经 基线评估",
    status: "RUNNING",
    stage: "UPLOAD",
    progress: 45,
    source: "REAL",
    createdAt: "2026-10-17T21:10:03.000Z",
    metrics: {},
    model: models[3],
  },
];

const deployments = [
  {
    id: "dpl_5b77c02a91",
    name: "划痕 v4 下发 · 一号工位",
    status: "ACTIVE",
    stage: "DONE",
    progress: 100,
    source: "REAL",
    deviceId: "dev_zynq_01",
    modelId: models[0].id,
    model: models[0],
    previousVersion: "V3.8.0",
    error: null,
    receipt: { resident: true },
    createdAt: "2026-10-16T12:31:52.000Z",
  },
  {
    id: "dpl_2c11fd88e0",
    name: "划痕 v4 下发 · 二号工位",
    status: "DOWNLOADING",
    stage: "TRANSFER",
    progress: 38,
    source: "REAL",
    deviceId: "dev_zynq_02",
    modelId: models[0].id,
    model: models[0],
    previousVersion: null,
    error: null,
    receipt: null,
    createdAt: "2026-10-17T21:40:11.000Z",
  },
  {
    id: "dpl_8aa902cd71",
    name: "划痕 v3 回退验证",
    status: "FAILED",
    stage: "SELF_TEST",
    progress: 82,
    source: "REAL",
    deviceId: "dev_zynq_01",
    modelId: models[1].id,
    model: models[1],
    previousVersion: "V4.2.1",
    error: "自检未通过：板端连续 3 帧推理超时（> 120ms），已保留原版本。",
    receipt: null,
    createdAt: "2026-10-13T18:05:20.000Z",
  },
  {
    id: "dpl_1f3e55aa02",
    name: "模拟模型初始部署",
    status: "SUPERSEDED",
    stage: "DONE",
    progress: 100,
    source: "SIMULATION",
    deviceId: "dev_zynq_02",
    modelId: models[2].id,
    model: models[2],
    previousVersion: "V1.0.2",
    error: null,
    receipt: null,
    createdAt: "2026-10-07T08:20:00.000Z",
  },
];

const device = {
  id: "dev_zynq_01",
  name: "领航者 Z7020 · 一号工位",
  type: "ZYNQ",
  connectionState: "ONLINE",
  runtimeState: "RUNNING",
  lastSeenAt: new Date().toISOString(),
  telemetry: { fps: 16.5, inferenceUs: 60400, cycleUs: 61000 },
  reportedState: { models: [{ version: "V4.2.1" }] },
  capabilities: { modelUpdate: true },
  error: null,
};

const datasets = [
  {
    id: "ds_71ab02",
    name: "表面缺陷 · 划痕 A 线",
    version: "4",
    status: "FROZEN",
    sourceCounts: { REAL: 412, SIMULATION: 0 },
    _count: { items: 412 },
    createdAt: "2026-10-14T10:00:00.000Z",
  },
  {
    id: "ds_22cd77",
    name: "药片缺角 · 小样本",
    version: "1",
    status: "FROZEN",
    sourceCounts: { REAL: 68, SIMULATION: 12 },
    _count: { items: 80 },
    createdAt: "2026-10-13T10:00:00.000Z",
  },
];

export function route(pathname) {
  if (pathname === "/api/auth/me")
    return { id: "usr_admin", name: "YUKINO", role: "ADMIN" };
  if (pathname === "/api/tasks") return page([]);
  if (pathname === "/api/devices/policy")
    return { staleMs: 10000, offlineMs: 30000, wsPath: "/ws" };
  if (pathname === "/api/devices/snapshot")
    return [device, { ...device, id: "dev_zynq_02", name: "领航者 Z7020 · 二号工位" }];
  if (pathname === "/api/models") return page(models);
  if (pathname.startsWith("/api/models/")) {
    const id = pathname.split("/")[3];
    return models.find((m) => m.id === id) ?? models[0];
  }
  if (pathname === "/api/trainings") return page(trainings);
  if (pathname === "/api/benchmarks") return page(benchmarks);
  if (pathname === "/api/deployments") return page(deployments);
  if (pathname === "/api/datasets") return page(datasets);
  return page([]);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href)
  createServer((req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    if (url.pathname === "/ws") return res.destroy();
    const body = route(url.pathname);
    res.writeHead(200, {
      "content-type": "application/json",
      "cache-control": "no-store",
    });
    res.end(JSON.stringify(body));
  }).listen(3000, "127.0.0.1", () => console.log("mock api on 3000"));
