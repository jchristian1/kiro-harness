import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwSetProjectAliasTool(client: WorkerClient) {
  return {
    name: "kw_set_project_alias",
    description:
      "Assign a friendly alias to a project so it can be referenced by name instead of project_id. " +
      "Aliases are case-insensitive and globally unique. " +
      "Returns the updated alias list or a conflict error if the alias is taken.",
    parameters: Type.Object({
      project_id: Type.String({ description: "The project ID to alias" }),
      alias: Type.String({ description: "The friendly alias to assign (e.g. 'fastapi harness')" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["project_id", "alias"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { project_id, alias } = parsed as { project_id: string; alias: string };

      const response = await client.post<Record<string, unknown>>(
        `/projects/${project_id}/aliases`,
        { alias }
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

      const aliases = (response["aliases"] as string[]) ?? [];
      const lines = [
        `✎ alias set — ${response["project_name"]} (${response["project_id"]})`,
        "",
        `aliases : ${aliases.length > 0 ? aliases.join(", ") : "(none)"}`,
        "",
        response["message"] as string,
      ];

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
