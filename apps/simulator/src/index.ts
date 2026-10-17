// The same simulator lives behind DeviceTransport in the local server.
// This CLI controls fault injection without introducing a second device protocol.
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";
const server = process.env.VISION_SERVER ?? "http://localhost:3000";
const prompt = createInterface({ input: stdin, output: stdout });
const username = await prompt.question("Simulator control username: ");
const password = await prompt.question("Password (input visible): ");
const login = await fetch(`${server}/api/auth/login`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ username, password }),
});
if (!login.ok) throw new Error("Authentication failed");
const { token } = (await login.json()) as { token: string };
const devices = (await fetch(`${server}/api/devices/snapshot`, {
  headers: { authorization: `Bearer ${token}` },
}).then((r) => r.json())) as { id: string; type: string; name: string }[];
const device = devices.find((d) => d.type === "SIMULATOR");
if (!device) throw new Error("Register a simulator device first");
console.log(`SIMULATED DEVICE: ${device.name}`);
console.log(
  "Faults: NONE NETWORK_LOST DEVICE_TIMEOUT INVALID_MODEL CHECKSUM_ERROR INFERENCE_ERROR DEPLOYMENT_FAILED LOW_FPS HIGH_LATENCY QUEUE_OVERFLOW",
);
for (;;) {
  const fault = await prompt.question("Fault (or quit): ");
  if (fault === "quit") break;
  const response = await fetch(`${server}/api/devices/${device.id}/commands`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ type: "FAULT", value: fault }),
  });
  console.log(response.status, await response.json());
}
prompt.close();
