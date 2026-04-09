/**
 * outputFormatter.ts — Normalize worker responses into stable tool output.
 */

import { type WorkerClient } from "./workerClient.js";

export interface RunResult {
  ok: boolean;
  project_id?: string;
  task_id?: string;
  run_id?: string;
  run_status?: string;
  artifact_headline?: string | null;
  findings_count?: number | null;
  recommended_next_step?: string | null;
  failure_reason?: string;
  error_code?: string;
  step?: string;
}

export interface StatusResult {
  ok: boolean;
  task_id?: string;
  status?: string;
  last_run_id?: string | null;
  last_run_mode?: string | null;
  last_run_status?: string | null;
  artifact_headline?: string | null;
  progress_message?: string | null;
  last_activity_at?: string | null;
  failure_reason?: string;
  error_code?: string;
  step?: string;
}

export async function formatRunResult(
  client: WorkerClient,
  projectId: string | null,
  taskId: string,
  run: Record<string, unknown>
): Promise<RunResult> {
  const result: RunResult = {
    ok: run["status"] === "completed",
    task_id: taskId,
    run_id: run["id"] as string | undefined,
    run_status: run["status"] as string | undefined,
    artifact_headline: null,
    findings_count: null,
    recommended_next_step: null,
  };
  if (projectId) result.project_id = projectId;

  if (run["status"] === "completed") {
    const runId = run["id"] as string;
    const artifact = await client.get<Record<string, unknown>>(
      `/runs/${runId}/artifact`
    );
    if (!("_http_error" in artifact)) {
      const content = (artifact["content"] as Record<string, unknown>) ?? {};
      result.artifact_headline = content["headline"] as string ?? null;
      result.findings_count = Array.isArray(content["findings"])
        ? content["findings"].length
        : null;
      result.recommended_next_step = content["recommended_next_step"] as string ?? null;
    }
  } else {
    result.failure_reason = run["failure_reason"] as string | undefined;
  }

  return result;
}

export function formatText(result: RunResult | StatusResult): string {
  const ok = result.ok;
  const icon = ok ? "✓" : "✗";
  const lines: string[] = [];

  if ("run_status" in result) {
    // RunResult
    const r = result as RunResult;
    lines.push(`${icon} run_status: ${r.run_status ?? "unknown"}`);
    if (r.artifact_headline) lines.push(`  headline: ${r.artifact_headline}`);
    if (r.recommended_next_step) lines.push(`  next_step: ${r.recommended_next_step}`);
    if (r.findings_count != null) lines.push(`  findings: ${r.findings_count}`);
    if (!ok && r.failure_reason) lines.push(`  reason: ${r.failure_reason}`);
    lines.push("");
    lines.push("IDs for follow-up commands:");
    if (r.project_id) lines.push(`  project_id : ${r.project_id}`);
    if (r.task_id) lines.push(`  task_id    : ${r.task_id}`);
    if (r.run_id) lines.push(`  run_id     : ${r.run_id}`);
  } else {
    // StatusResult
    const s = result as StatusResult;
    lines.push(`${icon} task status: ${s.status ?? "unknown"}`);
    if (s.progress_message) {
      const runningLabel = s.last_run_status === "running" ? "⟳ in progress" : "last progress";
      lines.push(`  ${runningLabel}: ${s.progress_message}`);
      if (s.last_activity_at) lines.push(`  last activity: ${s.last_activity_at}`);
    }
    if (s.artifact_headline) lines.push(`  headline: ${s.artifact_headline}`);
    if (!ok && s.failure_reason) lines.push(`  reason: ${s.failure_reason}`);
    lines.push("");
    lines.push("IDs for follow-up commands:");
    if (s.task_id) lines.push(`  task_id    : ${s.task_id}`);
    if (s.last_run_id) lines.push(`  run_id     : ${s.last_run_id}`);
    if (s.last_run_mode) lines.push(`  run_mode   : ${s.last_run_mode}`);
    if (s.last_run_status) lines.push(`  run_status : ${s.last_run_status}`);
  }

  return lines.join("\n");
}
