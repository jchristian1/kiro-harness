import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

const OUTCOME_ICON: Record<string, string> = {
  retried: "↺",
  needs_decision: "⚠",
  blocked: "✗",
  nothing_to_resume: "✓",
};

export function makeKwResumeProjectTool(client: WorkerClient) {
  return {
    name: "kw_resume_project",
    description:
      "Resume the most recent unfinished task for a project. " +
      "For failed or cancelled tasks: creates a fresh retry task and starts a non-blocking run. " +
      "For awaiting_revision (non-cancelled): returns needs_decision — PM must provide revision instructions. " +
      "For awaiting_approval: returns needs_decision — PM must approve. " +
      "For orphaned opening tasks: returns blocked — recommend close. " +
      "Returns immediately with outcome and task/run details.",
    parameters: Type.Object({
      project_id: Type.String({ description: "The project ID to resume" }),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["project_id"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const { project_id } = parsed as { project_id: string };

      const response = await client.post<Record<string, unknown>>(
        `/projects/${project_id}/resume`,
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
        `${icon} ${outcome.replace(/_/g, " ")} — project ${response["project_id"]}`,
        "",
      ];

      if (outcome === "retried") {
        lines.push(`new_task_id   : ${response["new_task_id"]}`);
        lines.push(`run_id        : ${response["run_id"]}`);
        lines.push(`prior_task_id : ${response["prior_task_id"]}`);
        lines.push(`prior_status  : ${response["prior_task_status"]}`);
        lines.push(`mode          : ${response["mode"]}`);
        lines.push(`task_status   : ${response["task_status"]}`);
        lines.push(`run_status    : ${response["run_status"]}`);
        lines.push(`workspace     : ${response["workspace_path"]}`);
      } else if (outcome === "needs_decision") {
        lines.push(`task_id       : ${response["task_id"]}`);
        lines.push(`task_status   : ${response["task_status"]}`);
        if (response["decision_type"]) lines.push(`decision      : ${response["decision_type"]}`);
      } else if (outcome === "blocked") {
        lines.push(`task_id       : ${response["task_id"] ?? "(none)"}`);
        if (response["block_reason"]) lines.push(`reason        : ${response["block_reason"]}`);
      }

      lines.push("");
      lines.push(response["message"] as string);

      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  };
}
