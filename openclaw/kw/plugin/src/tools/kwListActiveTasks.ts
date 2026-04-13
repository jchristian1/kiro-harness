import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwListActiveTasksTool(client: WorkerClient) {
  return {
    name: "kw_list_active_tasks",
    description:
      "List all currently active tasks across all projects. Shows what Kiro is doing right now. Read-only.",
    parameters: Type.Object({}),
    async execute(_id: string, params: unknown) {
      // No required params — accept empty object or envelope
      const parsed = parsePayload(params, []);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const response = await client.get<Record<string, unknown>>("/dashboard/active-tasks");
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      const tasks = (response["active_tasks"] as Record<string, unknown>[]) ?? [];
      const count = response["count"] as number ?? 0;

      if (count === 0) {
        return { content: [{ type: "text", text: "No active tasks right now.\n\nAll specialist runs are idle." }] };
      }

      const lines: string[] = [`⟳ ${count} active task${count !== 1 ? "s" : ""}`, ""];
      for (const t of tasks) {
        lines.push(`task_id    : ${t["task_id"]}`);
        lines.push(`project    : ${t["project_name"] ?? t["project_id"]}`);
        lines.push(`status     : ${t["task_status"]} / run ${t["run_status"] ?? "none"} (${t["run_mode"] ?? "?"})`);
        lines.push(`elapsed    : ${t["elapsed"] ?? "unknown"}`);
        if (t["progress_message"]) lines.push(`progress   : ${t["progress_message"]}`);
        lines.push(`description: ${t["description"]}`);
        lines.push("");
      }

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
