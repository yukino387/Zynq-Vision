# 本地开发与运行

Node >=22.12，pnpm 10.33。无需 Docker、公网服务或云存储（首次安装依赖需要包仓库访问）。

```powershell
pnpm install
pnpm dev
```

`pnpm dev` 首先运行 `pnpm run setup`，创建本地 .env、随机 JWT_SECRET/SEED_PASSWORD、SQLite 迁移及幂等 Seed，再启动 Server :3000、Web :5173、uni-app H5 :5174/mobile/。注意 `pnpm setup` 是 pnpm 自带命令；项目初始化必须使用 `pnpm run setup`。

初始用户 admin / engineer / operator，共用首次随机生成的 SEED_PASSWORD（在 .env 查看）。不要提交或在日志打印密码。种子记录全部标为 DEMO / SIMULATED。改动 SEED_PASSWORD 不会覆盖既有用户密码。

```powershell
pnpm build
pnpm start
```

生产 Web 为 `http://localhost:3000/`，移动端为 `/mobile/`。手机使用 Web“系统健康”中真实网卡地址，与服务器同一可互通局域网。防火墙策略由本机管理员管理。浏览器实时相机受 secure context/权限限制，不可用时使用系统相机或选图；原生真机需单独打包验证。

独立命令：dev:server、dev:web、dev:mobile、dev:simulator（交互故障控制 CLI）。后者使用同一服务端 SimulatorTransport，防止引入另一个虚构 Zynq 协议。

验证：`pnpm typecheck`、`pnpm lint`、`pnpm test`、`pnpm build`。自动测试使用 temporary/iot_platform_test/run-*/ 独立数据库和 storage，不修改实际板卡。hardware-check.ts 只读查询；hardware-capture.ts 会短暂接管并在 finally 恢复原暂停状态，只应确认没有其他上位机占用后执行。

原生 uni-app 工程源码已提供；当前构建命令验证 H5 产物，不代表已生成签名 APK/IPA 或经过手机相机/IMU 真机验收。
