-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "disabled" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Station" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Device" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "serialNumber" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "stationId" TEXT,
    "firmwareVersion" TEXT,
    "protocolVersion" TEXT,
    "ipAddress" TEXT,
    "lastSeenAt" DATETIME,
    "connectionState" TEXT NOT NULL DEFAULT 'OFFLINE',
    "runtimeState" TEXT NOT NULL DEFAULT 'UNKNOWN',
    "desiredState" JSONB NOT NULL DEFAULT '{}',
    "reportedState" JSONB NOT NULL DEFAULT '{}',
    "capabilities" JSONB NOT NULL,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Device_stationId_fkey" FOREIGN KEY ("stationId") REFERENCES "Station" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DeviceToken" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "deviceId" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "expiresAt" DATETIME,
    "revokedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "DeviceToken_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "Device" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "InspectionPlan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "version" INTEGER NOT NULL,
    "rules" JSONB NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Task" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'OPEN',
    "target" INTEGER NOT NULL,
    "stationId" TEXT,
    "planId" TEXT,
    "requirements" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Task_stationId_fkey" FOREIGN KEY ("stationId") REFERENCES "Station" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Task_planId_fkey" FOREIGN KEY ("planId") REFERENCES "InspectionPlan" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Workpiece" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "serialNumber" TEXT NOT NULL,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "CaptureSession" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "taskId" TEXT,
    "source" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "CaptureSession_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "Task" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "CaptureSet" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sessionId" TEXT,
    "clientId" TEXT NOT NULL,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "CaptureSet_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "CaptureSession" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Sample" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "clientId" TEXT NOT NULL,
    "idempotencyKey" TEXT NOT NULL,
    "localSequence" INTEGER NOT NULL DEFAULT 0,
    "taskId" TEXT,
    "captureSetId" TEXT,
    "hard" BOOLEAN NOT NULL DEFAULT false,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "capturedAt" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "deletedAt" DATETIME,
    CONSTRAINT "Sample_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "Task" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Sample_captureSetId_fkey" FOREIGN KEY ("captureSetId") REFERENCES "CaptureSet" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Asset" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sampleId" TEXT,
    "storageKey" TEXT NOT NULL,
    "originalName" TEXT NOT NULL,
    "mimeType" TEXT NOT NULL,
    "size" INTEGER NOT NULL,
    "sha256" TEXT NOT NULL,
    "width" INTEGER,
    "height" INTEGER,
    "format" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" DATETIME,
    CONSTRAINT "Asset_sampleId_fkey" FOREIGN KEY ("sampleId") REFERENCES "Sample" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "QualityReport" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sampleId" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "metrics" JSONB NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "QualityReport_sampleId_fkey" FOREIGN KEY ("sampleId") REFERENCES "Sample" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AnnotationSet" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sampleId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "version" INTEGER NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'DRAFT',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "AnnotationSet_sampleId_fkey" FOREIGN KEY ("sampleId") REFERENCES "Sample" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "AnnotationSet_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Annotation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "setId" TEXT NOT NULL,
    "classId" INTEGER NOT NULL,
    "label" TEXT NOT NULL,
    "x1" REAL NOT NULL,
    "y1" REAL NOT NULL,
    "x2" REAL NOT NULL,
    "y2" REAL NOT NULL,
    "confidence" REAL NOT NULL DEFAULT 1,
    CONSTRAINT "Annotation_setId_fkey" FOREIGN KEY ("setId") REFERENCES "AnnotationSet" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Inspection" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sampleId" TEXT NOT NULL,
    "deviceId" TEXT,
    "stationId" TEXT,
    "taskId" TEXT,
    "workpieceId" TEXT,
    "modelId" TEXT,
    "modelVersion" TEXT,
    "planVersion" TEXT,
    "firmwareVersion" TEXT,
    "frameId" INTEGER,
    "source" TEXT NOT NULL,
    "startedAt" DATETIME NOT NULL,
    "completedAt" DATETIME NOT NULL,
    "latency" REAL,
    "result" TEXT NOT NULL,
    "reason" TEXT NOT NULL,
    "confidence" REAL,
    "status" TEXT NOT NULL DEFAULT 'COMPLETED',
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Inspection_sampleId_fkey" FOREIGN KEY ("sampleId") REFERENCES "Sample" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Inspection_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "Device" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Inspection_stationId_fkey" FOREIGN KEY ("stationId") REFERENCES "Station" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Inspection_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "Task" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Inspection_workpieceId_fkey" FOREIGN KEY ("workpieceId") REFERENCES "Workpiece" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Inspection_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "Model" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Detection" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "inspectionId" TEXT NOT NULL,
    "classId" INTEGER NOT NULL,
    "label" TEXT NOT NULL,
    "confidence" REAL NOT NULL,
    "x1" REAL NOT NULL,
    "y1" REAL NOT NULL,
    "x2" REAL NOT NULL,
    "y2" REAL NOT NULL,
    CONSTRAINT "Detection_inspectionId_fkey" FOREIGN KEY ("inspectionId") REFERENCES "Inspection" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Review" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "inspectionId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "verdict" TEXT NOT NULL,
    "note" TEXT NOT NULL,
    "hard" BOOLEAN NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Review_inspectionId_fkey" FOREIGN KEY ("inspectionId") REFERENCES "Inspection" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Review_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Dataset" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "version" INTEGER NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'DRAFT',
    "checksum" TEXT,
    "frozenAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "DatasetItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "datasetId" TEXT NOT NULL,
    "sampleId" TEXT NOT NULL,
    "annotationSetId" TEXT NOT NULL,
    "split" TEXT NOT NULL DEFAULT 'train',
    "snapshot" JSONB NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "DatasetItem_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "Dataset" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "DatasetItem_sampleId_fkey" FOREIGN KEY ("sampleId") REFERENCES "Sample" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "DatasetItem_annotationSetId_fkey" FOREIGN KEY ("annotationSetId") REFERENCES "AnnotationSet" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "TrainingJob" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'QUEUED',
    "source" TEXT NOT NULL DEFAULT 'SIMULATION',
    "stage" TEXT NOT NULL DEFAULT 'Preparing Dataset',
    "progress" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "TrainingJob_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "Dataset" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Model" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "architecture" TEXT NOT NULL,
    "trainingId" TEXT,
    "manifest" JSONB NOT NULL,
    "source" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'CANDIDATE',
    "metrics" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Model_trainingId_fkey" FOREIGN KEY ("trainingId") REFERENCES "TrainingJob" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ModelArtifact" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "modelId" TEXT NOT NULL,
    "assetId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ModelArtifact_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "Model" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "ModelArtifact_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "Asset" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Benchmark" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "modelId" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "deviceId" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "metrics" JSONB NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Benchmark_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "Model" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Benchmark_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "Dataset" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Benchmark_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "Device" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Deployment" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "deviceId" TEXT NOT NULL,
    "modelId" TEXT NOT NULL,
    "previousVersion" TEXT,
    "status" TEXT NOT NULL DEFAULT 'APPROVED',
    "source" TEXT NOT NULL,
    "progress" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "receipt" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Deployment_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "Device" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Deployment_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "Model" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "SyncJob" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "clientId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'QUEUED',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "payload" JSONB NOT NULL,
    "startedAt" DATETIME,
    "completedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Job" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "type" TEXT NOT NULL,
    "entityId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'QUEUED',
    "payload" JSONB NOT NULL,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "startedAt" DATETIME,
    "completedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Command" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "deviceId" TEXT NOT NULL,
    "requestId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'QUEUED',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "result" JSONB,
    "error" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" DATETIME,
    CONSTRAINT "Command_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "Device" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DeviceEvent" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "deviceId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "requestId" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "DeviceEvent_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "Device" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "userId" TEXT,
    "action" TEXT NOT NULL,
    "entityId" TEXT NOT NULL,
    "before" JSONB,
    "after" JSONB,
    "requestId" TEXT NOT NULL,
    "result" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "AuditLog_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "SystemEvent" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "type" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "PairingToken" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "hash" TEXT NOT NULL,
    "expiresAt" DATETIME NOT NULL,
    "usedAt" DATETIME,
    "stationId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE UNIQUE INDEX "User_username_key" ON "User"("username");

-- CreateIndex
CREATE UNIQUE INDEX "Station_code_key" ON "Station"("code");

-- CreateIndex
CREATE UNIQUE INDEX "Device_serialNumber_key" ON "Device"("serialNumber");

-- CreateIndex
CREATE INDEX "Device_lastSeenAt_idx" ON "Device"("lastSeenAt");

-- CreateIndex
CREATE INDEX "Device_stationId_idx" ON "Device"("stationId");

-- CreateIndex
CREATE UNIQUE INDEX "DeviceToken_tokenHash_key" ON "DeviceToken"("tokenHash");

-- CreateIndex
CREATE UNIQUE INDEX "InspectionPlan_name_version_key" ON "InspectionPlan"("name", "version");

-- CreateIndex
CREATE UNIQUE INDEX "Workpiece_serialNumber_key" ON "Workpiece"("serialNumber");

-- CreateIndex
CREATE UNIQUE INDEX "CaptureSet_clientId_key" ON "CaptureSet"("clientId");

-- CreateIndex
CREATE UNIQUE INDEX "Sample_idempotencyKey_key" ON "Sample"("idempotencyKey");

-- CreateIndex
CREATE INDEX "Sample_createdAt_idx" ON "Sample"("createdAt");

-- CreateIndex
CREATE INDEX "Sample_source_idx" ON "Sample"("source");

-- CreateIndex
CREATE UNIQUE INDEX "Sample_clientId_localSequence_key" ON "Sample"("clientId", "localSequence");

-- CreateIndex
CREATE UNIQUE INDEX "Asset_storageKey_key" ON "Asset"("storageKey");

-- CreateIndex
CREATE INDEX "Asset_sha256_idx" ON "Asset"("sha256");

-- CreateIndex
CREATE UNIQUE INDEX "QualityReport_sampleId_key" ON "QualityReport"("sampleId");

-- CreateIndex
CREATE UNIQUE INDEX "AnnotationSet_sampleId_version_key" ON "AnnotationSet"("sampleId", "version");

-- CreateIndex
CREATE INDEX "Inspection_createdAt_idx" ON "Inspection"("createdAt");

-- CreateIndex
CREATE INDEX "Inspection_deviceId_idx" ON "Inspection"("deviceId");

-- CreateIndex
CREATE INDEX "Inspection_taskId_idx" ON "Inspection"("taskId");

-- CreateIndex
CREATE INDEX "Inspection_result_idx" ON "Inspection"("result");

-- CreateIndex
CREATE UNIQUE INDEX "Dataset_name_version_key" ON "Dataset"("name", "version");

-- CreateIndex
CREATE UNIQUE INDEX "DatasetItem_datasetId_sampleId_key" ON "DatasetItem"("datasetId", "sampleId");

-- CreateIndex
CREATE UNIQUE INDEX "Model_name_version_key" ON "Model"("name", "version");

-- CreateIndex
CREATE INDEX "Deployment_deviceId_status_idx" ON "Deployment"("deviceId", "status");

-- CreateIndex
CREATE INDEX "Job_status_createdAt_idx" ON "Job"("status", "createdAt");

-- CreateIndex
CREATE INDEX "DeviceEvent_deviceId_createdAt_idx" ON "DeviceEvent"("deviceId", "createdAt");

-- CreateIndex
CREATE INDEX "AuditLog_createdAt_idx" ON "AuditLog"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "PairingToken_hash_key" ON "PairingToken"("hash");
