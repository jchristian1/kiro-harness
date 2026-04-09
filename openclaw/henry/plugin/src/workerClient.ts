/**
 * workerClient.ts — Thin HTTP client for kiro-worker.
 * No business logic. Mirrors the worker API contract exactly.
 * Base URL is passed explicitly via createWorkerClient config — no env reads here.
 */

export interface WorkerClientConfig {
  baseUrl: string;
}

export interface WorkerClient {
  post: <T>(path: string, body: Record<string, unknown>) => Promise<T>;
  get: <T>(path: string) => Promise<T>;
}

async function request<T>(
  baseUrl: string,
  method: string,
  path: string,
  body?: Record<string, unknown>
): Promise<T> {
  const url = `${baseUrl}${path}`;
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) {
    (data as Record<string, unknown>)["_http_error"] = res.status;
  }
  return data as T;
}

export function createWorkerClient(config: WorkerClientConfig): WorkerClient {
  const { baseUrl } = config;
  return {
    post: <T>(path: string, body: Record<string, unknown>) =>
      request<T>(baseUrl, "POST", path, body),
    get: <T>(path: string) => request<T>(baseUrl, "GET", path),
  };
}
