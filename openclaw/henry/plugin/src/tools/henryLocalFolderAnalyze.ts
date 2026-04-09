import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { analyzeFlow } from "../analyzeFlow.js";
import { formatText } from "../outputFormatter.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeHenryLocalFolderAnalyzeTool(client: WorkerClient) {
  return {
    name: "henry_local_folder_analyze",
    description:
      "Open a local folder as a workspace and run a Kiro analysis. Returns structured artifact with tracing IDs.",
    parameters: Type.Object({
      name: Type.String({ description: "Unique project name" }),
      path: Type.String({ description: "Absolute path to local folder" }),
      description: Type.String({ description: "What to analyze" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["name", "path", "description"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const result = await analyzeFlow(
        client,
        parsed["name"] as string,
        "local_folder",
        parsed["path"] as string,
        parsed["description"] as string
      );
      const text = formatText(result);
      return {
        content: [{ type: "text", text: `${JSON.stringify(result, null, 2)}\n\n${text}` }],
      };
    },
  };
}
