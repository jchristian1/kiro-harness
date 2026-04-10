import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { analyzeFlow } from "../analyzeFlow.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryNewProjectAnalyzeTool(client: WorkerClient) {
  return {
    name: "kw_new_project_analyze",
    description:
      "Start a Kiro analysis on a brand-new project. Returns immediately with task_id, run_id, and status=analyzing. Use kw_task_status to poll progress and get the full structured result when complete.",
    parameters: Type.Object({
      name: Type.String({ description: "Unique project name" }),
      source_url: Type.String({
        description: "Absolute path where the new workspace will be created (must be under WORKSPACE_SAFE_ROOT)",
      }),
      description: Type.String({ description: "What to analyze or build" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["name", "source_url", "description"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const result = await analyzeFlow(
        client,
        parsed["name"] as string,
        "new_project",
        parsed["source_url"] as string,
        parsed["description"] as string
      );

      const summary = result.ok
        ? [
            `⟳ Analysis started`,
            `  task_id    : ${result.task_id}`,
            `  run_id     : ${result.run_id}`,
            `  status     : ${result.task_status}`,
            ``,
            `Poll progress with:`,
            `  /kw_task_status {"task_id":"${result.task_id}"}`,
          ].join("\n")
        : `✗ Failed at step: ${result.step}\n  reason: ${result.failure_reason}`;

      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${summary}` }],
      };
    },
  };
}
