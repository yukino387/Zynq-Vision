import { createApp } from "./bootstrap.js";
import { config } from "./config.js";
const app = await createApp();
await app.listen(config.SERVER_PORT, config.SERVER_HOST);
console.log(
  JSON.stringify({
    timestamp: new Date().toISOString(),
    level: "info",
    module: "bootstrap",
    message: `IoT Vision listening on http://localhost:${config.SERVER_PORT}`,
    requestId: null,
    entityId: null,
  }),
);
