import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

/**
 * kw_complete_task — Close a task that is in validating, awaiting_revision, or failed.
 * Used by the Project Lead when validation is not needed or not possible,
 * or when the implementation is complete and the task should be marked done.
 */
export function makeKwCompleteTaskTool(client: WorkerClient) {
  return {
    name: "kw_complete_task",
    description:
      "Close a task and mark it as done. Use when the task is in validating or awaiting_revision and the Project Lead decides no further action is needed.",
    parameters: Type.Object({
      task_id: Type.String({ description: "Task ID to close" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const taskId = parsed["task_id"] as string;

      const response = await client.post<Record<string, unknown>>(
        `/tasks/${taskId}/close`,
        {}
      );

      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: false, step: "close_task",
              failure_reason: err["message"] ?? "close failed",
              error_code: err["code"],
            }, null, 2),
          }],
        };
      }

      const newStatus = response["status"] as string;
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            ok: true,
            task_id: taskId,
            status: newStatus,
            message: "Task closed and marked as done.",
          }, null, 2),
        }],
      };
    },
  };
}
