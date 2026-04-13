import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

export function makeKwUpdateProjectSourceUrlTool(client: WorkerClient) {
  return {
    name: "kw_update_project_source_url",
    description:
      "Update a project's source_url in place when the original path has moved or changed. " +
      "Preserves project identity and task history. " +
      "Allowed for local_folder, local_repo, and github_repo projects. " +
      "Not allowed for new_project (managed path). " +
      "After updating, run kw_reinitialize_project_workspace to rebind the workspace.",
    parameters: Type.Object({
      project_id: Type.String({ description: "The project ID to update" }),
      source_url: Type.String({ description: "The new source path or URL" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["project_id", "source_url"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { project_id, source_url } = parsed as { project_id: string; source_url: string };

      const response = await client.post<Record<string, unknown>>(
        `/projects/${project_id}/source-url`,
        { source_url }
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

      const pathExists = response["path_exists"];
      const pathIcon = pathExists === true ? "✓" : pathExists === false ? "⚠" : "";

      const lines: string[] = [
        `✎ source_url updated — ${response["project_name"]} (${response["project_id"]})`,
        "",
        `source           : ${response["source"]}`,
        `old source_url   : ${response["old_source_url"] ?? "(none)"}`,
        `new source_url   : ${response["new_source_url"]}`,
      ];

      if (pathExists !== null && pathExists !== undefined) {
        lines.push(`path exists      : ${pathIcon} ${pathExists ? "yes" : "no"}`);
      }

      lines.push("");
      lines.push(response["message"] as string);

      if (response["next_step"] === "retry_recovery" && pathExists !== false) {
        lines.push("");
        lines.push("Next: run /kw_reinitialize_project_workspace to rebind the workspace.");
      }

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
