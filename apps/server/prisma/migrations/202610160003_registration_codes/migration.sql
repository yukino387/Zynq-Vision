CREATE TABLE "RegistrationCode" (
  "id" TEXT NOT NULL PRIMARY KEY,
  "codeHash" TEXT NOT NULL,
  "prefix" TEXT NOT NULL,
  "label" TEXT NOT NULL,
  "issuedById" TEXT NOT NULL,
  "expiresAt" DATETIME NOT NULL,
  "usedAt" DATETIME,
  "usedById" TEXT,
  "revokedAt" DATETIME,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX "RegistrationCode_codeHash_key" ON "RegistrationCode"("codeHash");
CREATE INDEX "RegistrationCode_createdAt_idx" ON "RegistrationCode"("createdAt");
