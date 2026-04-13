import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwListUnfinishedTasksTool(client: WorkerClient) {
  return {
    name: "kw_list_unfinished_tasks",
    description:
      "List all tasks that were started but not completed and are not currently active. " +
      "Includes failed, awaiting_revision, awaiting_approval, and stuck opening tasks. " +
      "Each result includes a resumability assessment and recommended next action. Read-only.",
    parameters: Type.Object({}),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, []);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const response = await client.get<Record<string, unknown>>("/dashboard/unfinished-tasks");
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      const tasks = (response["unfinished_tasks"] as Record<string, unknown>[]) ?? [];
      const count = response["count"] as number ?? 0;

      if (count === 0) {
        return { content: [{ type: "text", text: "No unfinished tasks found.\n\nAll tasks are either active, done, or never started." }] };
      }

      const lines: string[] = [`⚠ ${count} unfinished task${count !== 1 ? "s" : ""}`, ""];
      for (const t of tasks) {
        lines.push(`task_id    : ${t["task_id"]}`);
        lines.push(`project    : ${t["project_name"] ?? t["project_id"]}`);
        lines.push(`status     : ${t["task_status"]} / run ${t["run_status"] ?? "none"} (${t["run_mode"] ?? "?"})`);
        lines.push(`elapsed    : ${t["elapsed_unfinished"] ?? "unknown"}`);
        if (t["last_artifact_headline"]) lines.push(`last result: ${t["last_artifact_headline"]}`);
        lines.push(`resumable  : ${t["resumable"] ? `yes (${t["resume_confidence"]} confidence)` : "no"}`);
        lines.push(`note       : ${t["resume_note"]}`);
        lines.push(`next action: ${t["recommended_action"]}`);
        lines.push(`description: ${t["description"]}`);
        lines.push("");
      }

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
