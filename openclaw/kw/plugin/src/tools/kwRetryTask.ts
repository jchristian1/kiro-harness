import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwRetryTaskTool(client: WorkerClient) {
  return {
    name: "kw_retry_task",
    description:
      "Retry a failed, cancelled, or unfinished task by creating a fresh task with the same " +
      "parameters and immediately starting a non-blocking run. " +
      "Allowed for tasks in: failed, awaiting_revision, awaiting_approval. " +
      "Returns immediately with new task_id, run_id, and status=running.",
    parameters: Type.Object({
      task_id: Type.String({ description: "The task ID to retry" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { task_id } = parsed as { task_id: string };

      const response = await client.post<Record<string, unknown>>(
        `/tasks/${task_id}/retry`,
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

      const lines = [
        `↺ retry started — ${response["mode"]} run`,
        "",
        `new_task_id    : ${response["new_task_id"]}`,
        `run_id         : ${response["run_id"]}`,
        `prior_task_id  : ${response["prior_task_id"]}`,
        `prior_status   : ${response["prior_task_status"]}`,
        `task_status    : ${response["task_status"]}`,
        `run_status     : ${response["run_status"]}`,
        `workspace      : ${response["workspace_path"]}`,
        `retry_type     : ${response["retry_type"]}`,
        "",
        response["message"] as string,
      ];

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
