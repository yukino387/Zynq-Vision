-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Review" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "inspectionId" TEXT,
    "sampleId" TEXT,
    "userId" TEXT NOT NULL,
    "verdict" TEXT NOT NULL,
    "note" TEXT NOT NULL,
    "hard" BOOLEAN NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Review_inspectionId_fkey" FOREIGN KEY ("inspectionId") REFERENCES "Inspection" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Review_sampleId_fkey" FOREIGN KEY ("sampleId") REFERENCES "Sample" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Review_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_Review" ("createdAt", "hard", "id", "inspectionId", "note", "userId", "verdict") SELECT "createdAt", "hard", "id", "inspectionId", "note", "userId", "verdict" FROM "Review";
DROP TABLE "Review";
ALTER TABLE "new_Review" RENAME TO "Review";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
