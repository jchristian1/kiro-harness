import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

const MATCH_ICON: Record<string, string> = {
  id: "🔑",
  name: "📛",
  alias: "✎",
  not_found: "✗",
};

export function makeKwResolveProjectTool(client: WorkerClient) {
  return {
    name: "kw_resolve_project",
    description:
      "Resolve a project by id, canonical name, or alias. " +
      "Returns the project_id, canonical name, aliases, and how the query matched. " +
      "Use this to find a project before running other kw commands.",
    parameters: Type.Object({
      query: Type.String({ description: "Project id, canonical name, or alias to look up" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["query"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { query } = parsed as { query: string };

      const response = await client.get<Record<string, unknown>>(
        `/projects/resolve?query=${encodeURIComponent(query)}`
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

      const matchType = response["match_type"] as string;
      const icon = MATCH_ICON[matchType] ?? "?";
      const aliases = (response["aliases"] as string[]) ?? [];

      const lines = [
        `${icon} matched by ${matchType} — "${response["query"]}"`,
        "",
        `project_id   : ${response["project_id"]}`,
        `name         : ${response["project_name"]}`,
        `source       : ${response["source"]}`,
        `aliases      : ${aliases.length > 0 ? aliases.join(", ") : "(none)"}`,
        `workspace_id : ${response["workspace_id"] ?? "(none)"}`,
      ];

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
