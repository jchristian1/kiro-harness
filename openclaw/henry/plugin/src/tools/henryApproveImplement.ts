import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { formatRunResult, formatText } from "../outputFormatter.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryApproveImplementTool(client: WorkerClient) {
  return {
    name: "henry_approve_implement",
    description:
      "Approve a task in awaiting_approval state and trigger the implementation run. Use henry_task_status to confirm state first.",
    parameters: Type.Object({
      task_id: Type.String({ description: "Task ID in awaiting_approval state" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const taskId = parsed["task_id"] as string;

      // 1. Approve
      const approved = await client.post<Record<string, unknown>>(
        `/tasks/${taskId}/approve`,
        {}
      );
      if ("_http_error" in approved) {
        const err = (approved["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: false, task_id: taskId, step: "approve",
              failure_reason: err["message"] ?? "approve failed",
              error_code: err["code"],
            }, null, 2),
          }],
        };
      }

      // 2. Trigger implement run
      const run = await client.post<Record<string, unknown>>(
        `/tasks/${taskId}/runs`,
        { mode: "implement" }
      );
      if ("_http_error" in run) {
        const err = (run["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: false, task_id: taskId, step: "trigger_run",
              failure_reason: err["message"] ?? "trigger run failed",
              error_code: err["code"],
            }, null, 2),
          }],
        };
      }

      const result = await formatRunResult(client, null, taskId, run);
      const text = formatText(result);
      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${text}` }],
      };
    },
  };
}
