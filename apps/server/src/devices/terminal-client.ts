import type { Device } from "@prisma/client";
import { config } from "../config.js";
import { DomainError } from "../core/errors.js";

function terminalHost(device: Device) {
  const metadata = device.metadata as Record<string, unknown>;
  return typeof metadata.terminalAddress === "string" &&
    metadata.terminalAddress
    ? metadata.terminalAddress
    : config.ZYNQ_HOST;
}

export async function terminalPreviewStream(
  device: Device,
  signal: AbortSignal,
) {
  const response = await fetch(
    `http://${terminalHost(device)}:8880/preview-stream`,
    {
      signal,
    },
  );
  if (
    !response.ok ||
    !response.body ||
    response.headers.get("content-type") !== "application/x-vision-frame-stream"
  )
    throw new DomainError("UNAVAILABLE", "设备预览流不可用", 503);
  return response.body;
}

export async function terminalRequest(
  device: Device,
  path: string,
  authorization: string,
  body?: unknown,
  timeout = 10000,
) {
  let response: Response;
  try {
    response = await fetch(`http://${terminalHost(device)}:8879${path}`, {
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
