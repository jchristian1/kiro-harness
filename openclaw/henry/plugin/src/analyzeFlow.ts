/**
 * analyzeFlow.ts — Shared flow: create project + workspace + task + analyze run.
 * Accepts a WorkerClient injected from the plugin entrypoint.
 */

import { type WorkerClient } from "./workerClient.js";
import { formatRunResult, type RunResult } from "./outputFormatter.js";

export async function analyzeFlow(
  client: WorkerClient,
  name: string,
  source: string,
  sourceUrl: string,
  description: string
): Promise<RunResult> {
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

  // 4. Trigger analyze run (blocks until complete)
  const run = await client.post<Record<string, unknown>>(
    `/tasks/${taskId}/runs`,
    { mode: "analyze" }
  );
  if ("_http_error" in run) {
    const err = (run["error"] as Record<string, string>) ?? {};
    return { ok: false, step: "trigger_run", failure_reason: err["message"] ?? "trigger run failed", error_code: err["code"] };
  }

  return formatRunResult(client, projectId, taskId, run);
}
