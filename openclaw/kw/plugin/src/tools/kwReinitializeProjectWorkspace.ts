import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

const OUTCOME_ICON: Record<string, string> = {
  already_healthy: "✓",
  rebound: "↺",
  recreated: "✦",
  blocked: "✗",
};

export function makeKwReinitializeProjectWorkspaceTool(client: WorkerClient) {
  return {
    name: "kw_reinitialize_project_workspace",
    description:
      "Recover a project's canonical workspace when it is missing or invalid. " +
      "For local_folder/local_repo: rebinds to the source path if it still exists. " +
      "For github_repo: re-clones into the managed workspace path. " +
      "For new_project: recreates the managed directory. " +
      "Returns outcome (already_healthy | rebound | recreated | blocked) and workspace details.",
    parameters: Type.Object({
      project_id: Type.String({ description: "The project ID to recover" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["project_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { project_id } = parsed as { project_id: string };

      const response = await client.post<Record<string, unknown>>(
        `/projects/${project_id}/workspace/reinitialize`,
        {}
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

      const outcome = response["outcome"] as string;
      const icon = OUTCOME_ICON[outcome] ?? "?";

      const lines: string[] = [
        `${icon} ${outcome.replace("_", " ")} — ${response["project_name"]} (${response["project_id"]})`,
        "",
        `source           : ${response["source"]}`,
        `outcome          : ${outcome}`,
      ];

      if (response["workspace_id"]) {
        lines.push(`workspace_id     : ${response["workspace_id"]}`);
      }
      if (response["workspace_path"]) {
        lines.push(`workspace_path   : ${response["workspace_path"]}`);
      }
      if (response["previous_workspace_id"]) {
        lines.push(`previous_ws_id   : ${response["previous_workspace_id"]}`);
      }
      lines.push(`reason           : ${response["reason"]}`);
      lines.push("");
      lines.push(response["message"] as string);

      if (outcome === "blocked") {
        lines.push("");
        lines.push("Next steps:");
        lines.push("• For local_folder: ensure the source path exists on disk, then retry.");
        lines.push("• For github_repo: check network access and source_url, then retry.");
        lines.push("• Or create a new project pointing to the correct source.");
      } else if (outcome !== "already_healthy") {
        lines.push("");
        lines.push("Follow-up tasks can now reuse this workspace via /kw_implement or /kw_github_analyze.");
      }

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
