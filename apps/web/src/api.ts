import type { ApiError } from "@vision/contracts";
import { errorMessage } from "@vision/shared";
export class RequestError extends Error {
  constructor(
    public code: string,
    message: string,
    public requestId: string,
    public status: number,
  ) {
    super(errorMessage(code, message));
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = sessionStorage.getItem("vision.token");
  const headers = new Headers(options.headers);
  if (token) headers.set("authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("content-type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const e = (await response.json().catch(() => ({
      code: "NETWORK_ERROR",
      message: response.statusText,
      requestId: "",
    }))) as ApiError;
    throw new RequestError(e.code, e.message, e.requestId, response.status);
  }
  return response.json() as Promise<T>;
}
export async function blob(path: string, method = "GET") {
  const response = await fetch(`/api${path}`, {
    method,
    headers: {
      authorization: `Bearer ${sessionStorage.getItem("vision.token") ?? ""}`,
    },
  });
  if (!response.ok) {
    const e = (await response.json()) as ApiError;
    throw new RequestError(e.code, e.message, e.requestId, response.status);
  }
  return response.blob();
}
export async function download(path: string, name: string, method = "GET") {
  const url = URL.createObjectURL(await blob(path, method));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export function errorText(error: unknown) {
  return error instanceof RequestError
    ? error.message
    : error instanceof Error
      ? error.message
      : String(error);
}
