import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

/**
 * kw_cancel_task — Stop an active specialist run cleanly.
 *
 * Kills the kiro-cli subprocess if still running, marks the run as cancelled,
 * and transitions the task to awaiting_revision so it can be retried or closed.
 *
 * Use when a run is stuck, wrong, or no longer wanted.
 */
export function makeKwCancelTaskTool(client: WorkerClient) {
  return {
    name: "kw_cancel_task",
    description:
      "Stop an active specialist run. Use when a task is stuck, wrong, or no longer wanted. Kills the active kiro-cli process, marks the run as cancelled, and transitions the task to awaiting_revision.",
    parameters: Type.Object({
      task_id: Type.String({ description: "Task ID of the active task to cancel" }),
      reason: Type.Optional(Type.String({ description: "Why this task is being cancelled (optional)" })),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const taskId = parsed["task_id"] as string;
      const reason = parsed["reason"] as string | undefined;

      const body: Record<string, unknown> = {};
      if (reason) body["reason"] = reason;

      const response = await client.post<Record<string, unknown>>(
        `/tasks/${taskId}/cancel`,
        body
      );

      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: false, step: "cancel_task",
              failure_reason: err["message"] ?? "cancel failed",
              error_code: err["code"],
            }, null, 2),
          }],
        };
      }

      const result = {
        ok: true,
        task_id: response["task_id"],
        run_id: response["run_id"],
        previous_task_status: response["previous_task_status"],
        previous_run_status: response["previous_run_status"],
        new_task_status: response["new_task_status"],
        new_run_status: response["new_run_status"],
        message: response["message"],
      };

      const summary = [
        `✗ Task cancelled`,
        `  task_id    : ${result.task_id}`,
        `  run_id     : ${result.run_id}`,
        `  was        : ${result.previous_task_status} / run ${result.previous_run_status}`,
        `  now        : ${result.new_task_status} / run ${result.new_run_status}`,
        ``,
        `${result.message}`,
      ].join("\n");

      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${summary}` }],
      };
    },
  };
}
