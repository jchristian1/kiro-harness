import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { analyzeFlow } from "../analyzeFlow.js";
import { formatText } from "../outputFormatter.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryGithubAnalyzeTool(client: WorkerClient) {
  return {
    name: "henry_github_analyze",
    description:
      "Clone a GitHub repo, open its workspace, and run a Kiro analysis. Returns structured artifact with tracing IDs.",
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
      const text = formatText(result);
      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${text}` }],
      };
    },
  };
}
