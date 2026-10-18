-- PS 应用固件包与每台设备的 OTA 部署记录。
CREATE TABLE "Firmware" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "sha256" TEXT NOT NULL,
    "size" INTEGER NOT NULL,
    "imageSize" INTEGER NOT NULL,
    "entry" INTEGER NOT NULL,
    "segments" JSONB NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'READY',
    "notes" TEXT,
    "assetId" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Firmware_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "Asset" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "Firmware_version_key" ON "Firmware"("version");

CREATE TABLE "FirmwareDeployment" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "deviceId" TEXT NOT NULL,
    "firmwareId" TEXT NOT NULL,
    "previousVersion" TEXT,
    "previousSha256" TEXT,
    "previousSlot" INTEGER,
    "status" TEXT NOT NULL DEFAULT 'APPROVED',
    "progress" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "receipt" JSONB NOT NULL DEFAULT '{}',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "FirmwareDeployment_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "Device" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "FirmwareDeployment_firmwareId_fkey" FOREIGN KEY ("firmwareId") REFERENCES "Firmware" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX "FirmwareDeployment_deviceId_status_idx" ON "FirmwareDeployment"("deviceId", "status");
CREATE INDEX "FirmwareDeployment_firmwareId_idx" ON "FirmwareDeployment"("firmwareId");
