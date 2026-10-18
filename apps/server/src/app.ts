import "reflect-metadata";
import { Module, Global } from "@nestjs/common";
import { APP_GUARD, APP_INTERCEPTOR } from "@nestjs/core";
import { JwtModule } from "@nestjs/jwt";
import { config } from "./config.js";
import { Db } from "./core/db.js";
import { Events } from "./core/events.js";
import { AuthGuard, AuthController } from "./core/auth.js";
import { RegistrationController } from "./core/registration.js";
import { Audit } from "./core/audit.js";
import { DevicesService } from "./devices/devices.service.js";
import { CommandsService } from "./devices/commands.service.js";
import { DevicesController } from "./devices/devices.controller.js";
import {
  UsersController,
  StationsController,
  TasksController,
  WorkpiecesController,
  PlansController,
} from "./resources/resources.controller.js";
import { AssetsService } from "./assets/assets.service.js";
import { SamplesService } from "./samples/samples.service.js";
import { BatchesController } from "./inspections/batches.controller.js";
import { TerminalController } from "./inspections/terminal.controller.js";
import {
  SamplesController,
  AssetsController,
} from "./samples/samples.controller.js";
import {
  InspectionsController,
  ReviewsController,
} from "./inspections/inspections.controller.js";
import { DatasetsService } from "./datasets/datasets.service.js";
import { DatasetsController } from "./datasets/datasets.controller.js";
import { ModelsService } from "./models/models.service.js";
import {
  ModelsController,
  TrainingsController,
} from "./models/models.controller.js";
import { DeploymentsController } from "./deployments/deployments.controller.js";
import { FirmwareService } from "./firmware/firmware.service.js";
import { FirmwareController } from "./firmware/firmware.controller.js";
import { JobsService } from "./jobs/jobs.service.js";
import { TrainingService } from "./models/training.service.js";
import { SystemController } from "./system/system.controller.js";
import { FileJobsService } from "./datasets/file-jobs.service.js";
@Global()
@Module({
  imports: [
    JwtModule.register({
      secret: config.JWT_SECRET,
      signOptions: {
        expiresIn: "8h",
        issuer: "iot-vision-platform",
        audience: "vision-local",
      },
      verifyOptions: {
        issuer: "iot-vision-platform",
        audience: "vision-local",
      },
    }),
  ],
  providers: [Db, Events, AssetsService],
  exports: [Db, Events, AssetsService, JwtModule],
})
class CoreModule {}
@Module({
  providers: [DevicesService, CommandsService],
  controllers: [DevicesController],
  exports: [DevicesService, CommandsService],
})
class DevicesModule {}
@Module({
  imports: [DevicesModule],
  providers: [SamplesService, DatasetsService, FileJobsService],
  exports: [FileJobsService],
  controllers: [
    SamplesController,
    AssetsController,
    InspectionsController,
    ReviewsController,
    BatchesController,
    TerminalController,
    DatasetsController,
  ],
})
class DataModule {}
@Module({
  imports: [DevicesModule],
  providers: [ModelsService, TrainingService],
  exports: [ModelsService, TrainingService],
  controllers: [ModelsController, TrainingsController, DeploymentsController],
})
class ModelsModule {}
@Module({
  imports: [DevicesModule],
  providers: [FirmwareService],
  exports: [FirmwareService],
  controllers: [FirmwareController],
})
class FirmwareModule {}
@Module({
  imports: [DevicesModule, DataModule, ModelsModule, FirmwareModule],
  providers: [JobsService],
})
class JobsModule {}
@Module({
  imports: [
    CoreModule,
    DevicesModule,
    DataModule,
    ModelsModule,
    FirmwareModule,
    JobsModule,
  ],
  controllers: [
    AuthController,
    RegistrationController,
    UsersController,
    StationsController,
    TasksController,
    WorkpiecesController,
    PlansController,
    SystemController,
  ],
  providers: [
    { provide: APP_GUARD, useClass: AuthGuard },
    { provide: APP_INTERCEPTOR, useClass: Audit },
  ],
})
export class AppModule {}
