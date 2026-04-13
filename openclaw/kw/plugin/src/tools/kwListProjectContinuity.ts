import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

const STATUS_ICON: Record<string, string> = {
  healthy: "✓",
  stale: "~",
  invalid: "✗",
  missing: "✗",
};

export function makeKwListProjectContinuityTool(client: WorkerClient) {
  return {
    name: "kw_list_project_continuity",
    description:
      "Portfolio-level project continuity audit. Shows workspace health, unfinished task counts, " +
      "active task counts, and recommended PM action for every project. " +
      "Use this to identify which projects are healthy, which have unfinished work, " +
      "and which need re-initialization. Read-only.",
    parameters: Type.Object({}),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, []);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const response = await client.get<Record<string, unknown>>("/dashboard/project-continuity");
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      const projects = (response["projects"] as Record<string, unknown>[]) ?? [];
      const count = response["count"] as number ?? 0;
      const summary = (response["summary"] as Record<string, number>) ?? {};

      if (count === 0) {
        return { content: [{ type: "text", text: "No projects found." }] };
      }

      const summaryParts: string[] = [];
      if (summary["invalid"]) summaryParts.push(`${summary["invalid"]} invalid`);
      if (summary["missing"]) summaryParts.push(`${summary["missing"]} missing workspace`);
      if (summary["active"]) summaryParts.push(`${summary["active"]} active`);
      if (summary["unfinished"]) summaryParts.push(`${summary["unfinished"]} unfinished`);
      if (summary["stale"]) summaryParts.push(`${summary["stale"]} stale`);
      if (summary["healthy"]) summaryParts.push(`${summary["healthy"]} healthy`);

      const lines: string[] = [
        `${count} project${count !== 1 ? "s" : ""} — ${summaryParts.join(", ")}`,
        "",
      ];

      for (const p of projects) {
        const wsStatus = p["workspace_status"] as string;
        const icon = STATUS_ICON[wsStatus] ?? "?";
        const unfinished = p["unfinished_task_count"] as number;
        const active = p["active_task_count"] as number;

        lines.push(`${icon} ${p["project_name"]} (${p["project_id"]})`);
        lines.push(`  workspace : ${wsStatus}${p["workspace_path"] ? ` — ${p["workspace_path"]}` : ""}`);
        if (active > 0) lines.push(`  active    : ${active} task${active !== 1 ? "s" : ""} running`);
        if (unfinished > 0) {
          lines.push(`  unfinished: ${unfinished} task${unfinished !== 1 ? "s" : ""}`);
          if (p["most_recent_unfinished_task_id"]) {
            lines.push(`  latest    : ${p["most_recent_unfinished_task_id"]}`);
          }
        }
        lines.push(`  last seen : ${p["elapsed_since_activity"] ?? "unknown"} ago`);
        lines.push(`  action    : ${p["recommended_action"]}`);
        lines.push("");
      }

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
