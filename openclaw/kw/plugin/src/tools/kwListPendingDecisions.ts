import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwListPendingDecisionsTool(client: WorkerClient) {
  return {
    name: "kw_list_pending_decisions",
    description:
      "List all tasks that need Project Manager attention or a decision. Shows what is waiting, why, and what to do next. Read-only.",
    parameters: Type.Object({}),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, []);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const response = await client.get<Record<string, unknown>>("/dashboard/pending-decisions");
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      const decisions = (response["pending_decisions"] as Record<string, unknown>[]) ?? [];
      const count = response["count"] as number ?? 0;

      if (count === 0) {
        return { content: [{ type: "text", text: "No tasks currently need PM attention.\n\nAll tasks are either active or complete." }] };
      }

      const lines: string[] = [`⚠ ${count} task${count !== 1 ? "s" : ""} need${count === 1 ? "s" : ""} attention`, ""];
      for (const d of decisions) {
        lines.push(`task_id    : ${d["task_id"]}`);
        lines.push(`project    : ${d["project_name"] ?? d["project_id"]}`);
        lines.push(`status     : ${d["task_status"]} / run ${d["run_status"] ?? "none"}`);
        lines.push(`reason     : ${d["reason"]}`);
        lines.push(`next       : ${d["next_action"]}`);
        if (d["elapsed_waiting"]) lines.push(`waiting    : ${d["elapsed_waiting"]}`);
        lines.push("");
      }

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
