import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { analyzeFlow } from "../analyzeFlow.js";
import { formatText } from "../outputFormatter.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryNewProjectAnalyzeTool(client: WorkerClient) {
  return {
    name: "henry_new_project_analyze",
    description:
      "Create a brand-new project from scratch, open its workspace, and run a Kiro analysis. Source is always new_project.",
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
      const text = formatText(result);
      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${text}` }],
      };
    },
  };
}
