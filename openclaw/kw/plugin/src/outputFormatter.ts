/**
 * outputFormatter.ts — Normalize worker responses into stable tool output.
 * Surfaces the full structured Kiro artifact so the Project Lead can present
 * complete results to the user without guessing from a one-line headline.
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
  already_satisfied?: boolean | null;
  changes_summary?: string | null;
  failure_reason?: string;
  error_code?: string;
  step?: string;
  _artifact?: Record<string, unknown> | null;
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
  _artifact?: Record<string, unknown> | null;
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
    already_satisfied: null,
    changes_summary: null,
    _artifact: null,
  };
  if (projectId) result.project_id = projectId;

  if (run["status"] === "completed") {
    const runId = run["id"] as string;
    const artifact = await client.get<Record<string, unknown>>(`/runs/${runId}/artifact`);
    if (!("_http_error" in artifact)) {
      const content = (artifact["content"] as Record<string, unknown>) ?? {};
      result.artifact_headline = content["headline"] as string ?? null;
      result.findings_count = Array.isArray(content["findings"]) ? content["findings"].length : null;
      result.recommended_next_step = content["recommended_next_step"] as string ?? null;
      result.already_satisfied = content["already_satisfied"] as boolean ?? null;
      result.changes_summary = content["changes_summary"] as string ?? null;
      result._artifact = content;
    }
  } else {
    result.failure_reason = run["failure_reason"] as string | undefined;
  }

  return result;
}

function _formatList(items: unknown[], maxItems = 10): string {
  if (!Array.isArray(items) || items.length === 0) return "  (none)";
  return items
    .slice(0, maxItems)
    .map((item) => `  • ${String(item)}`)
    .join("\n");
}

function _formatFileChanges(files: unknown[]): string {
  if (!Array.isArray(files) || files.length === 0) return "  (none)";
  return files
    .map((f) => {
      const fc = f as Record<string, string>;
      return `  [${fc["action"] ?? "?"}] ${fc["path"] ?? "?"} — ${fc["description"] ?? ""}`;
    })
    .join("\n");
}

export function formatText(result: RunResult | StatusResult): string {
  const ok = result.ok;
  const icon = ok ? "✓" : "✗";
  const lines: string[] = [];

  if ("run_status" in result) {
    const r = result as RunResult;
    const artifact = r._artifact ?? {};

    // Outcome label
    let outcomeLabel = r.run_status ?? "unknown";
    if (r.run_status === "completed") {
      if (r.already_satisfied === true) outcomeLabel = "completed — already satisfied";
      else if (r.recommended_next_step === "request_review") outcomeLabel = "completed with warnings — review needed";
      else if (r.recommended_next_step === "needs_follow_up") outcomeLabel = "completed — follow-up needed";
      else outcomeLabel = "completed";
    } else if (r.run_status === "parse_failed" || r.run_status === "error") {
      outcomeLabel = "failed";
    }

    lines.push(`${icon} ${outcomeLabel}`);
    lines.push("");

    // Headline
    if (r.artifact_headline) {
      lines.push(`RESULT: ${r.artifact_headline}`);
      lines.push("");
    }

    if (r.already_satisfied === true) {
      lines.push("ℹ️  ALREADY SATISFIED — no code change was needed");
      lines.push("");
    }

    // Findings (analyze) or Changes summary (implement)
    const mode = artifact["mode"] as string ?? "";

    if (mode === "analyze") {
      const findings = artifact["findings"] as string[] ?? [];
      if (findings.length > 0) {
        lines.push("FINDINGS:");
        lines.push(_formatList(findings));
        lines.push("");
      }
      const steps = artifact["implementation_steps"] as string[] ?? [];
      if (steps.length > 0) {
        lines.push("RECOMMENDED STEPS:");
        lines.push(_formatList(steps));
        lines.push("");
      }
      const risks = artifact["risks"] as string[] ?? [];
      if (risks.length > 0) {
        lines.push("RISKS:");
        lines.push(_formatList(risks));
        lines.push("");
      }
      const tradeoffs = artifact["tradeoffs"] as string[] ?? [];
      if (tradeoffs.length > 0) {
        lines.push("TRADEOFFS:");
        lines.push(_formatList(tradeoffs));
        lines.push("");
      }
      const questions = artifact["questions"] as string[] ?? [];
      if (questions.length > 0) {
        lines.push("OPEN QUESTIONS:");
        lines.push(_formatList(questions));
        lines.push("");
      }
    }

    if (mode === "implement") {
      if (r.changes_summary) {
        lines.push("WHAT HAPPENED:");
        lines.push(`  ${r.changes_summary}`);
        lines.push("");
      }
      const files = artifact["files_changed"] as unknown[] ?? [];
      if (files.length > 0) {
        lines.push("FILES CHANGED:");
        lines.push(_formatFileChanges(files));
        lines.push("");
      }
      const validationRun = artifact["validation_run"] as string | null ?? null;
      if (validationRun) {
        lines.push("VALIDATION:");
        lines.push(`  ${validationRun}`);
        lines.push("");
      }
      const knownIssues = artifact["known_issues"] as string[] ?? [];
      if (knownIssues.length > 0) {
        lines.push("KNOWN ISSUES / BLOCKERS:");
        lines.push(_formatList(knownIssues));
        lines.push("");
      }
      const followUps = artifact["follow_ups"] as string[] ?? [];
      if (followUps.length > 0) {
        lines.push("FOLLOW-UPS:");
        lines.push(_formatList(followUps));
        lines.push("");
      }
    }

    if (mode === "validate") {
      const passed = artifact["passed"] as boolean ?? false;
      lines.push(`VALIDATION: ${passed ? "✓ passed" : "✗ failed"}`);
      const issues = artifact["issues_found"] as string[] ?? [];
      if (issues.length > 0) {
        lines.push("ISSUES FOUND:");
        lines.push(_formatList(issues));
        lines.push("");
      }
      const cmds = artifact["commands_run"] as string[] ?? [];
      if (cmds.length > 0) {
        lines.push("COMMANDS RUN:");
        lines.push(_formatList(cmds));
        lines.push("");
      }
    }

    // Next step
    if (r.recommended_next_step) {
      const nextStepLabels: Record<string, string> = {
        "run_validation": "Run validation to verify the changes",
        "request_review": "Request human review before proceeding",
        "needs_follow_up": "Follow-up work is needed",
        "approve_and_implement": "Ready to implement — approve to proceed",
        "no_action_needed": "No action needed",
        "request_clarification": "Clarification needed before proceeding",
        "mark_done": "Mark as done",
        "request_revision": "Revision needed",
        "retry_validation": "Retry validation",
      };
      const label = nextStepLabels[r.recommended_next_step] ?? r.recommended_next_step;
      lines.push(`NEXT STEP: ${label}`);
      lines.push("");
    }

    if (!ok && r.failure_reason) {
      lines.push(`FAILURE: ${r.failure_reason}`);
      lines.push("");
    }

    lines.push("IDs:");
    if (r.project_id) lines.push(`  project_id : ${r.project_id}`);
    if (r.task_id) lines.push(`  task_id    : ${r.task_id}`);
    if (r.run_id) lines.push(`  run_id     : ${r.run_id}`);

  } else {
    // StatusResult
    const s = result as StatusResult;
    const artifact = s._artifact ?? {};

    let statusLabel = s.status ?? "unknown";
    if (s.status === "awaiting_revision") {
      if (s.last_run_status === "cancelled") {
        statusLabel = "cancelled — run was stopped; use /kw_implement to retry or /kw_complete_task to close";
      } else {
        statusLabel = "awaiting revision — needs direction or follow-up";
      }
    }
    else if (s.status === "done") statusLabel = "done — specialist run complete";
    else if (s.status === "implementing") statusLabel = "implementing — run in progress";
    else if (s.status === "analyzing") statusLabel = "analyzing — run in progress";

    lines.push(`${icon} ${statusLabel}`);
    lines.push("");

    if (s.progress_message) {
      const label = s.last_run_status === "running" ? "⟳ in progress" : "last activity";
      lines.push(`${label}: ${s.progress_message}`);
      if (s.last_activity_at) lines.push(`last seen: ${s.last_activity_at}`);
      lines.push("");
    }

    // If we have a full artifact, show the rich report
    if (artifact && Object.keys(artifact).length > 0) {
      const mode = artifact["mode"] as string ?? "";
      const headline = artifact["headline"] as string ?? s.artifact_headline ?? null;
      if (headline) {
        lines.push(`RESULT: ${headline}`);
        lines.push("");
      }

      if (mode === "analyze") {
        const findings = artifact["findings"] as string[] ?? [];
        if (findings.length > 0) {
          lines.push("FINDINGS:");
          lines.push(_formatList(findings));
          lines.push("");
        }
        const steps = artifact["implementation_steps"] as string[] ?? [];
        if (steps.length > 0) {
          lines.push("RECOMMENDED STEPS:");
          lines.push(_formatList(steps));
          lines.push("");
        }
        const risks = artifact["risks"] as string[] ?? [];
        if (risks.length > 0) {
          lines.push("RISKS:");
          lines.push(_formatList(risks));
          lines.push("");
        }
      }

      if (mode === "implement") {
        const changesSummary = artifact["changes_summary"] as string ?? null;
        if (changesSummary) {
          lines.push("WHAT HAPPENED:");
          lines.push(`  ${changesSummary}`);
          lines.push("");
        }
        const files = artifact["files_changed"] as unknown[] ?? [];
        if (files.length > 0) {
          lines.push("FILES CHANGED:");
          lines.push(_formatFileChanges(files));
          lines.push("");
        }
        const knownIssues = artifact["known_issues"] as string[] ?? [];
        if (knownIssues.length > 0) {
          lines.push("KNOWN ISSUES:");
          lines.push(_formatList(knownIssues));
          lines.push("");
        }
      }

      const rns = artifact["recommended_next_step"] as string ?? null;
      if (rns) {
        const nextStepLabels: Record<string, string> = {
          "run_validation": "Run validation",
          "request_review": "Request review",
          "needs_follow_up": "Follow-up needed",
          "approve_and_implement": "Ready to implement",
          "no_action_needed": "No action needed",
          "mark_done": "Mark as done",
          "request_revision": "Revision needed",
        };
        lines.push(`NEXT STEP: ${nextStepLabels[rns] ?? rns}`);
        lines.push("");
      }
    } else if (s.artifact_headline) {
      lines.push(`RESULT: ${s.artifact_headline}`);
      lines.push("");
    }

    if (!ok && s.failure_reason) {
      lines.push(`FAILURE: ${s.failure_reason}`);
      lines.push("");
    }

    lines.push("IDs:");
    if (s.task_id) lines.push(`  task_id    : ${s.task_id}`);
    if (s.last_run_id) lines.push(`  run_id     : ${s.last_run_id}`);
    if (s.last_run_mode) lines.push(`  run_mode   : ${s.last_run_mode}`);
    if (s.last_run_status) lines.push(`  run_status : ${s.last_run_status}`);
  }

  return lines.join("\n");
}
