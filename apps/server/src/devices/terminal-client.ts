import type { Device } from "@prisma/client";
import { config } from "../config.js";
import { DomainError } from "../core/errors.js";

export async function terminalRequest(
  device: Device,
  path: string,
  authorization: string,
  body?: unknown,
  timeout = 10000,
) {
  const metadata = device.metadata as Record<string, unknown>;
  const host =
    typeof metadata.terminalAddress === "string" && metadata.terminalAddress
      ? metadata.terminalAddress
      : config.ZYNQ_HOST;
  let response: Response;
  try {
    response = await fetch(`http://${host}:8879${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { authorization, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeout),
    });
  } catch {
    throw new DomainError("UNAVAILABLE", "设备暂时不可达，请检查连接", 503);
  }
  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      message = (JSON.parse(text) as { error?: string }).error ?? text;
    } catch {
      /* Plain device response. */
    }
    throw new DomainError(
      "COMMAND_REJECTED",
      message || "设备操作失败",
      response.status,
    );
  }
  return response;
}
