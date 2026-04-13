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
      "active task counts, shared-path warnings, and recommended PM action for every project. " +
      "Use this to identify which projects are healthy, which have unfinished work, " +
      "which share a workspace path, and which need re-initialization. Read-only.",
    parameters: Type.Object({
      include_archived: Type.Optional(Type.Boolean({ description: "Include archived projects (default: false)" })),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, []);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const includeArchived = (parsed["include_archived"] as boolean | undefined) ?? false;
      const url = includeArchived
        ? "/dashboard/project-continuity?include_archived=true"
        : "/dashboard/project-continuity";

      const response = await client.get<Record<string, unknown>>(url);
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
      if (summary["shared_path"]) summaryParts.push(`${summary["shared_path"]} shared path`);
      if (summary["active"]) summaryParts.push(`${summary["active"]} active`);
      if (summary["unfinished"]) summaryParts.push(`${summary["unfinished"]} unfinished`);
      if (summary["stale"]) summaryParts.push(`${summary["stale"]} stale`);
      if (summary["healthy"]) summaryParts.push(`${summary["healthy"]} healthy`);
      const archivedHidden = summary["archived_hidden"] as number ?? 0;
      if (archivedHidden > 0 && !includeArchived) {
        summaryParts.push(`${archivedHidden} archived (hidden)`);
      }
      if (includeArchived && summary["archived_shown"]) {
        summaryParts.push(`${summary["archived_shown"]} archived (shown)`);
      }

      const lines: string[] = [
        `${count} project${count !== 1 ? "s" : ""} — ${summaryParts.join(", ")}`,
        "",
      ];

      for (const p of projects) {
        const wsStatus = p["workspace_status"] as string;
        const icon = STATUS_ICON[wsStatus] ?? "?";
        const unfinished = p["unfinished_task_count"] as number;
        const active = p["active_task_count"] as number;
        const sharedWarning = p["shared_path_warning"] as string | null;
        const aliases = (p["aliases"] as string[]) ?? [];

        // Header: icon + canonical name + aliases (if any) + id
        const aliasStr = aliases.length > 0 ? ` [${aliases.join(", ")}]` : "";
        const archivedTag = p["archived"] ? " [archived]" : "";
        lines.push(`${icon} ${p["project_name"]}${aliasStr}${archivedTag} (${p["project_id"]})`);
        lines.push(`  workspace : ${wsStatus}${p["workspace_path"] ? ` — ${p["workspace_path"]}` : ""}`);
        if (sharedWarning) {
          lines.push(`  ⚠ shared  : ${sharedWarning}`);
        }
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
