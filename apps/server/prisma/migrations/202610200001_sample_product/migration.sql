ALTER TABLE "Sample" ADD COLUMN "planId" TEXT REFERENCES "InspectionPlan"("id") ON DELETE SET NULL ON UPDATE CASCADE;
UPDATE "Sample" SET "planId" = (SELECT "planId" FROM "Task" WHERE "Task"."id" = "Sample"."taskId");
ALTER TABLE "Device" ADD COLUMN "desiredJobId" TEXT;
