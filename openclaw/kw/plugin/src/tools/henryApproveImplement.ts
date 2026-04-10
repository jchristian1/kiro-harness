import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryApproveImplementTool(client: WorkerClient) {
  return {
    name: "kw_approve_implement",
    description:
      "Approve a task in awaiting_approval state and start the implementation run. Returns immediately with task_id, run_id, and status=implementing. Use kw_task_status to poll progress.",
    parameters: Type.Object({
      task_id: Type.String({ description: "Task ID in awaiting_approval state" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const taskId = parsed["task_id"] as string;

      // 1. Approve — synchronous state transition
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

      // 2. Start implement run asynchronously — returns immediately
      const startResponse = await client.post<Record<string, unknown>>(
        `/tasks/${taskId}/runs/start`,
        { mode: "implement" }
      );
      if ("_http_error" in startResponse) {
        const err = (startResponse["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: false, task_id: taskId, step: "start_run",
              failure_reason: err["message"] ?? "start run failed",
              error_code: err["code"],
            }, null, 2),
          }],
        };
      }

      const result = {
        ok: true,
        task_id: startResponse["task_id"] as string,
        run_id: startResponse["run_id"] as string,
        task_status: startResponse["task_status"] as string,
        run_status: "running",
        message: startResponse["message"] as string,
      };

      const summary = [
        `⟳ Implementation started`,
        `  task_id    : ${result.task_id}`,
        `  run_id     : ${result.run_id}`,
        `  status     : ${result.task_status}`,
        ``,
        `Poll progress with:`,
        `  /kw_task_status {"task_id":"${result.task_id}"}`,
      ].join("\n");

      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${summary}` }],
      };
    },
  };
}
