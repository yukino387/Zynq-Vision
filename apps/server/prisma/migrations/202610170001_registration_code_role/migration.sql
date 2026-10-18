-- 注册码携带目标角色；存量注册码一律按操作员处理。
ALTER TABLE "RegistrationCode" ADD COLUMN "role" TEXT NOT NULL DEFAULT 'OPERATOR';
