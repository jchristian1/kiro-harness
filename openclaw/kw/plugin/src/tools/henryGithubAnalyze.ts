import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { analyzeFlow } from "../analyzeFlow.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryGithubAnalyzeTool(client: WorkerClient) {
  return {
    name: "kw_github_analyze",
    description:
      "Start a Kiro analysis on a GitHub repo. Returns immediately with task_id, run_id, and status=analyzing. Use kw_task_status to poll progress and get the full structured result when complete.",
    parameters: Type.Object({
      name: Type.String({ description: "Unique project name" }),
      repo_url: Type.String({ description: "Full GitHub HTTPS URL" }),
      description: Type.String({ description: "What to analyze" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["name", "repo_url", "description"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const result = await analyzeFlow(
        client,
        parsed["name"] as string,
        "github_repo",
        parsed["repo_url"] as string,
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
