import {
  Injectable,
  type OnModuleInit,
  type OnModuleDestroy,
} from "@nestjs/common";
import { PrismaClient } from "@prisma/client";
@Injectable()
export class Db extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  async onModuleInit() {
    await this.$connect();
    await this.$queryRawUnsafe("PRAGMA journal_mode=WAL");
    await this.$executeRawUnsafe("PRAGMA foreign_keys=ON");
    await this.$queryRawUnsafe("PRAGMA busy_timeout=5000");
  }
  async onModuleDestroy() {
    await this.$disconnect();
  }
}
