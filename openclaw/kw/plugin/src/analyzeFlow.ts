/**
 * analyzeFlow.ts — Shared non-blocking flow for all analysis-type runs.
 * Creates project + workspace + task, starts analyze run asynchronously,
 * and returns immediately with task_id, run_id, and active status.
 *
 * The run executes in the background. Use kw_task_status to poll progress
 * and retrieve the full structured result when complete.
 */

import { type WorkerClient } from "./workerClient.js";

export interface AnalyzeStartResult {
  ok: boolean;
  project_id?: string;
  task_id?: string;
  run_id?: string;
  task_status?: string;
  run_status?: string;
  message?: string;
  step?: string;
  failure_reason?: string;
  error_code?: string;
}

export async function analyzeFlow(
  client: WorkerClient,
  name: string,
  source: string,
  sourceUrl: string,
  description: string
): Promise<AnalyzeStartResult> {
  // 1. Create project
  const proj = await client.post<Record<string, unknown>>("/projects", {
    name,
    source,
    source_url: sourceUrl,
  });
  if ("_http_error" in proj) {
    const err = (proj["error"] as Record<string, string>) ?? {};
    return { ok: false, step: "create_project", failure_reason: err["message"] ?? "create project failed", error_code: err["code"] };
  }
  const projectId = proj["id"] as string;

  // 2. Open workspace
  const ws = await client.post<Record<string, unknown>>(
    `/projects/${projectId}/workspaces`,
    {}
  );
  if ("_http_error" in ws) {
    const err = (ws["error"] as Record<string, string>) ?? {};
    return { ok: false, step: "open_workspace", failure_reason: err["message"] ?? "open workspace failed", error_code: err["code"] };
  }

  // 3. Create task
  const task = await client.post<Record<string, unknown>>("/tasks", {
    project_id: projectId,
    intent: "analyze_codebase",
    source,
    operation: "analyze_then_approve",
    description,
  });
  if ("_http_error" in task) {
    const err = (task["error"] as Record<string, string>) ?? {};
    return { ok: false, step: "create_task", failure_reason: err["message"] ?? "create task failed", error_code: err["code"] };
  }
  const taskId = task["id"] as string;

  // 4. Start analyze run asynchronously — returns immediately with run_id
  const startResponse = await client.post<Record<string, unknown>>(
    `/tasks/${taskId}/runs/start`,
    { mode: "analyze" }
  );
  if ("_http_error" in startResponse) {
    const err = (startResponse["error"] as Record<string, string>) ?? {};
    return { ok: false, step: "start_run", failure_reason: err["message"] ?? "start run failed", error_code: err["code"] };
  }

  return {
    ok: true,
    project_id: projectId,
    task_id: startResponse["task_id"] as string,
    run_id: startResponse["run_id"] as string,
    task_status: startResponse["task_status"] as string,
    run_status: "running",
    message: startResponse["message"] as string,
  };
}
