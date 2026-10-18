CREATE TABLE "InspectionBatch" (
 "id" TEXT NOT NULL PRIMARY KEY,
 "name" TEXT NOT NULL,
 "deviceId" TEXT NOT NULL,
 "taskId" TEXT NOT NULL,
 "target" INTEGER NOT NULL,
 "status" TEXT NOT NULL DEFAULT 'OPEN',
 "execution" TEXT NOT NULL DEFAULT 'HOST',
 "snapshot" JSONB NOT NULL,
 "createdBy" TEXT NOT NULL,
 "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 "closedAt" DATETIME
);
ALTER TABLE "Inspection" ADD COLUMN "batchId" TEXT REFERENCES "InspectionBatch"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "Inspection" ADD COLUMN "acquisitionId" TEXT;
ALTER TABLE "Inspection" ADD COLUMN "reviewResult" TEXT;
ALTER TABLE "Review" ADD COLUMN "finalResult" TEXT;
CREATE INDEX "Inspection_batchId_idx" ON "Inspection"("batchId");
CREATE UNIQUE INDEX "Inspection_batchId_acquisitionId_key" ON "Inspection"("batchId", "acquisitionId");
CREATE INDEX "InspectionBatch_deviceId_status_idx" ON "InspectionBatch"("deviceId", "status");
CREATE INDEX "InspectionBatch_taskId_idx" ON "InspectionBatch"("taskId");
CREATE UNIQUE INDEX "InspectionBatch_open_device_key" ON "InspectionBatch"("deviceId") WHERE "status" = 'OPEN';
