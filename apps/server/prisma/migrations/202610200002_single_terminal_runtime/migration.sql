-- One runtime: batches are platform-side production runs grouped by the board's run id.
UPDATE "InspectionBatch" SET "status" = 'CLOSED', "closedAt" = CURRENT_TIMESTAMP WHERE "status" = 'OPEN';
ALTER TABLE "Device" DROP COLUMN "desiredJobId";
ALTER TABLE "InspectionBatch" DROP COLUMN "execution";
ALTER TABLE "InspectionBatch" ADD COLUMN "productionRunId" TEXT;
CREATE UNIQUE INDEX "InspectionBatch_deviceId_productionRunId_key" ON "InspectionBatch"("deviceId", "productionRunId");
