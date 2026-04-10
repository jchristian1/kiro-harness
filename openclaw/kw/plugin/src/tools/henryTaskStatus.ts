import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { formatText, type StatusResult } from "../outputFormatter.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryTaskStatusTool(client: WorkerClient) {
  return {
    name: "kw_task_status",
    description:
      "Get the full status and structured result of a task. For active runs, shows current progress. For completed runs, shows the full Kiro report including findings, files changed, validation, blockers, risks, follow-ups, and next step.",
    parameters: Type.Object({
      task_id: Type.String({ description: "Task ID to check" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const taskId = parsed["task_id"] as string;
      const task = await client.get<Record<string, unknown>>(`/tasks/${taskId}`);

      if ("_http_error" in task) {
        const err = (task["error"] as Record<string, string>) ?? {};
        const result: StatusResult = {
          ok: false,
          task_id: taskId,
          step: "get_task",
          failure_reason: err["message"] ?? "get task failed",
          error_code: err["code"],
        };
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      const lastRun = task["last_run"] as Record<string, unknown> | null;
      const result: StatusResult = {
        ok: true,
        task_id: taskId,
        status: task["status"] as string,
        last_run_id: (lastRun?.["id"] as string) ?? null,
        last_run_mode: (lastRun?.["mode"] as string) ?? null,
        last_run_status: (lastRun?.["status"] as string) ?? null,
        artifact_headline: null,
        progress_message: (lastRun?.["progress_message"] as string) ?? null,
        last_activity_at: (lastRun?.["last_activity_at"] as string) ?? null,
      };

      if (lastRun?.["status"] === "completed") {
        const runId = lastRun["id"] as string;
        const artifact = await client.get<Record<string, unknown>>(`/runs/${runId}/artifact`);
        if (!("_http_error" in artifact)) {
          const content = (artifact["content"] as Record<string, unknown>) ?? {};
          result.artifact_headline = (content["headline"] as string) ?? null;
          (result as Record<string, unknown>)["_artifact"] = content;
        }
      }

      const text = formatText(result);
      const { _artifact, ...resultForJson } = result as Record<string, unknown>;
      void _artifact;
      return {
        content: [{ type: "text", text: `${JSON.stringify(resultForJson, null, 2)}\n\n${text}` }],
      };
    },
  };
}
