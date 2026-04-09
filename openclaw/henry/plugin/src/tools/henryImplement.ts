import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { formatRunResult, formatText } from "../outputFormatter.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

/**
 * henry_implement — Create a new implementation task on an existing project
 * and trigger the implement run immediately.
 *
 * Fetches the analysis artifact from the completed analysis task and embeds
 * the implementation_steps + headline into the new task description so
 * kiro-cli has the context it needs to produce structured JSON output.
 *
 * Flow:
 *   1. GET /tasks/{task_id} to get project_id and source
 *   2. GET /tasks/{task_id}/runs + GET /runs/{run_id}/artifact to get analysis context
 *   3. Create new task (operation: implement_now) with enriched description
 *   4. Trigger implement run immediately
 *   5. Return normalized result with tracing IDs
 */
export function makeHenryImplementTool(client: WorkerClient) {
  return {
    name: "henry_implement",
    description:
      "Create a new implementation task on an existing project and run it immediately. Use after a completed analysis task when the user approves implementation. Requires task_id from the completed analysis task.",
    parameters: Type.Object({
      task_id: Type.String({ description: "Task ID from the completed analysis task" }),
      description: Type.String({ description: "What to implement — be specific and bounded to ONE change" }),
      intent: Type.Optional(Type.String({ description: "Intent for this task (default: add_feature)" })),
      step_index: Type.Optional(Type.Number({ description: "Which implementation step to execute (0-based index, default: 0 = first step)" })),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["task_id", "description"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const analysisTaskId = parsed["task_id"] as string;
      const userDescription = parsed["description"] as string;
      const intent = (parsed["intent"] as string | undefined) ?? "add_feature";
      const stepIndex = typeof parsed["step_index"] === "number" ? parsed["step_index"] : 0;

      // 1. Get the completed analysis task to extract project_id and source
      const analysisTask = await client.get<Record<string, unknown>>(`/tasks/${analysisTaskId}`);
      if ("_http_error" in analysisTask) {
        const err = (analysisTask["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: false, step: "get_analysis_task",
              failure_reason: err["message"] ?? "analysis task not found",
              error_code: err["code"] ?? "NOT_FOUND",
            }, null, 2),
          }],
        };
      }

      const projectId = analysisTask["project_id"] as string;
      const source = analysisTask["source"] as string;

      // 2. Fetch the analysis artifact to give kiro-cli implementation context
      let enrichedDescription = userDescription;
      const runs = await client.get<Record<string, unknown>>(`/tasks/${analysisTaskId}/runs`);
      if (!("_http_error" in runs)) {
        const runList = (runs["runs"] as Record<string, unknown>[]) ?? [];
        const completedAnalyzeRun = runList.find(
          (r) => r["mode"] === "analyze" && r["status"] === "completed"
        );
        if (completedAnalyzeRun) {
          const artifact = await client.get<Record<string, unknown>>(
            `/runs/${completedAnalyzeRun["id"]}/artifact`
          );
          if (!("_http_error" in artifact)) {
            const content = (artifact["content"] as Record<string, unknown>) ?? {};
            const headline = content["headline"] as string ?? "";
            const steps = (content["implementation_steps"] as string[]) ?? [];
            const findings = (content["findings"] as string[]) ?? [];
            // Embed analysis context into description so kiro-cli has what it needs
            const contextBlock = [
              `User request: ${userDescription}`,
              "",
              `Analysis headline: ${headline}`,
              "",
              findings.length > 0 ? `Key findings:\n${findings.slice(0, 3).map((f) => `- ${f}`).join("\n")}` : "",
              "",
              steps.length > 0
                ? `Implement ONLY this one step (do not attempt other steps):\n${steps[stepIndex] ?? steps[0]}`
                : "",
              "",
              "After completing this single change, output the JSON summary.",
            ].filter(Boolean).join("\n");
            enrichedDescription = contextBlock;
          }
        }
      }

      // 3. Create new implementation task on the same project
      const task = await client.post<Record<string, unknown>>("/tasks", {
        project_id: projectId,
        intent,
        source,
        operation: "implement_now",
        description: enrichedDescription,
      });
      if ("_http_error" in task) {
        const err = (task["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: false, step: "create_task",
              failure_reason: err["message"] ?? "create task failed",
              error_code: err["code"],
            }, null, 2),
          }],
        };
      }
      const taskId = task["id"] as string;

      // 4. Trigger implement run
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
              ok: false, step: "trigger_run",
              failure_reason: err["message"] ?? "trigger run failed",
              error_code: err["code"],
            }, null, 2),
          }],
        };
      }

      const result = await formatRunResult(client, projectId, taskId, run);
      const text = formatText(result);
      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${text}` }],
      };
    },
  };
}
