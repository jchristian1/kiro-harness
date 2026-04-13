import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwGetProjectWorkspaceTool(client: WorkerClient) {
  return {
    name: "kw_get_project_workspace",
    description:
      "Get the canonical workspace for a project. Shows which workspace path is active, " +
      "when it was last used, and whether it is a reused or freshly created workspace. " +
      "Use this to verify workspace continuity before starting follow-up work. Read-only.",
    parameters: Type.Object({
      project_id: Type.String({ description: "The project ID to inspect" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["project_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { project_id } = parsed as { project_id: string };

      const response = await client.get<Record<string, unknown>>(`/projects/${project_id}/workspace`);
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      const lines: string[] = ["Workspace", ""];
      lines.push(`workspace_id     : ${response["id"]}`);
      lines.push(`project_id       : ${response["project_id"]}`);
      lines.push(`path             : ${response["path"]}`);
      if (response["git_remote"]) lines.push(`git_remote       : ${response["git_remote"]}`);
      if (response["git_branch"]) lines.push(`git_branch       : ${response["git_branch"]}`);
      lines.push(`created_at       : ${response["created_at"]}`);
      lines.push(`last_accessed_at : ${response["last_accessed_at"]}`);

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
