import type { Device } from "@prisma/client";
import type { Capabilities, TerminalStatus } from "@vision/contracts";
import type { Db } from "../core/db.js";
export const terminalCapabilities: Capabilities = {
  capture: false,
  preview: false,
  inference: true,
  modelUpdate: false,
  firmwareUpdate: false,
  localStorage: true,
  offlineInference: true,
  offlineSync: true,
  modelVersion: true,
  planUpdate: false,
  restartInference: false,
};
export function isLinuxTerminal(device: Pick<Device, "type" | "metadata">) {
  const metadata = device.metadata as Record<string, unknown>;
  return (
    device.type === "ZYNQ" &&
    (metadata.runtimeProfile === "LINUX_TERMINAL" || !!metadata.terminal)
  );
}
export async function terminalStatus(
  db: Db,
  device: Device,
): Promise<TerminalStatus> {
  const metadata = device.metadata as Record<string, unknown>;
  const state = metadata.terminal as
    | (NonNullable<TerminalStatus["state"]> & { credentialId: string })
    | undefined;
  const credential = state
    ? await db.deviceToken.findUnique({ where: { id: state.credentialId } })
    : await db.deviceToken.findFirst({
        where: {
          deviceId: device.id,
          revokedAt: null,
          OR: [{ expiresAt: null }, { expiresAt: { gt: new Date() } }],
        },
      });
  const bound =
    !!credential &&
    !credential.revokedAt &&
    (!credential.expiresAt || credential.expiresAt > new Date());
  if (!state) return { bound, online: false, lastSeenAt: null, state: null };
  const age = Date.now() - Date.parse(state.receivedAt);
  const { credentialId: _credentialId, ...reported } = state;
  return {
    bound,
    online: bound && age >= 0 && age <= 20000,
    lastSeenAt: state.receivedAt,
    state: reported,
  };
}
