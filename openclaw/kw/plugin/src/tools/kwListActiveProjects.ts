import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwListActiveProjectsTool(client: WorkerClient) {
  return {
    name: "kw_list_active_projects",
    description:
      "List all projects that currently have active specialist work in progress. Read-only.",
    parameters: Type.Object({}),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, []);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const response = await client.get<Record<string, unknown>>("/dashboard/active-projects");
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      const projects = (response["active_projects"] as Record<string, unknown>[]) ?? [];
      const count = response["count"] as number ?? 0;

      if (count === 0) {
        return { content: [{ type: "text", text: "No active projects right now.\n\nAll projects are idle." }] };
      }

      const lines: string[] = [`⟳ ${count} active project${count !== 1 ? "s" : ""}`, ""];
      for (const p of projects) {
        const taskCount = p["active_task_count"] as number ?? 0;
        lines.push(`project    : ${p["project_name"] ?? p["project_id"]}`);
        lines.push(`project_id : ${p["project_id"]}`);
        lines.push(`active     : ${taskCount} task${taskCount !== 1 ? "s" : ""}`);
        lines.push(`status     : ${p["most_recent_task_status"] ?? "unknown"}`);
        if (p["most_recent_progress"]) lines.push(`progress   : ${p["most_recent_progress"]}`);
        if (p["last_activity_at"]) lines.push(`last seen  : ${p["last_activity_at"]}`);
        lines.push("");
      }

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
