import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

/**
 * kw_validate_task — Start a validation run for a completed or awaiting-revision task.
 *
 * Non-blocking: creates a new task on the same project and starts a validate run
 * in the background. Returns immediately with new_task_id and run_id.
 *
 * Use kw_task_status to poll progress and see the full validation report when done.
 */
export function makeKwValidateTaskTool(client: WorkerClient) {
  return {
    name: "kw_validate_task",
    description:
      "Start a validation run for a completed or awaiting-revision implementation task. " +
      "Non-blocking — returns immediately with new task_id and run_id. " +
      "Use kw_task_status to check progress and see the full validation report. " +
      "Allowed source task states: done, awaiting_revision, validating.",
    parameters: Type.Object({
      task_id: Type.String({ description: "Task ID of the implementation task to validate" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { task_id } = parsed as { task_id: string };

      const response = await client.post<Record<string, unknown>>(
        `/tasks/${task_id}/validate`,
        {}
      );
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      const newTaskId = response["new_task_id"] as string;
      const runId = response["run_id"] as string;

      const lines = [
        `⟳ Validation started`,
        "",
        `new_task_id    : ${newTaskId}`,
        `run_id         : ${runId}`,
        `prior_task_id  : ${response["prior_task_id"]}`,
        `prior_status   : ${response["prior_task_status"]}`,
        `task_status    : ${response["task_status"]}`,
        `run_status     : ${response["run_status"]}`,
        `workspace      : ${response["workspace_path"]}`,
        "",
        response["message"] as string,
        "",
        `Poll progress with:`,
        `  /kw_task_status {"task_id":"${newTaskId}"}`,
      ];

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
