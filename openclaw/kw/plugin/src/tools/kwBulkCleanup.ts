import { Type } from "@sinclair/typebox";
import { type WorkerClient } from "../workerClient.js";
import { parsePayload, isPayloadError, payloadErrorResponse } from "../parsePayload.js";

type CleanupMode = "duplicate_tasks" | "stale_tasks" | "dead_projects";

const MODE_ENDPOINT: Record<CleanupMode, string> = {
  duplicate_tasks: "/cleanup/duplicate-tasks",
  stale_tasks: "/cleanup/stale-tasks",
  dead_projects: "/cleanup/dead-projects",
};

const MODE_LABEL: Record<CleanupMode, string> = {
  duplicate_tasks: "Duplicate dead task cleanup",
  stale_tasks: "Stale active task cleanup",
  dead_projects: "Dead project archive",
};

function formatCleanupResult(mode: CleanupMode, r: Record<string, unknown>): string {
  const dryRun = r["dry_run"] as boolean;
  const prefix = dryRun ? "[DRY RUN] " : "";
  const lines: string[] = [
    `${prefix}${MODE_LABEL[mode]}`,
    "",
    `message : ${r["message"]}`,
    "",
  ];

  const criteria = r["criteria"] as Record<string, unknown> ?? {};
  lines.push("Criteria:");
  for (const [k, v] of Object.entries(criteria)) {
    const val = Array.isArray(v) ? v.join(", ") : String(v);
    lines.push(`  ${k}: ${val}`);
  }
  lines.push("");

  const actionKey = mode === "duplicate_tasks" ? "closed" : mode === "stale_tasks" ? "cancelled" : "archived";
  const actionCount = r[`${actionKey}_count`] as number ?? 0;
  const skippedCount = r["skipped_count"] as number ?? 0;
  const items = (r[actionKey] as Record<string, unknown>[]) ?? [];
  const skipped = (r["skipped"] as Record<string, unknown>[]) ?? [];

  if (actionCount > 0) {
    lines.push(`${dryRun ? "Would " : ""}${actionKey.charAt(0).toUpperCase() + actionKey.slice(1)} (${actionCount}):`);
    for (const item of items.slice(0, 20)) {
      if (mode === "duplicate_tasks") {
        lines.push(`  ✗ ${item["task_id"]} — ${item["reason"]}`);
        lines.push(`    kept: ${item["kept_task_id"]}`);
      } else if (mode === "stale_tasks") {
        lines.push(`  ✗ ${item["task_id"]} (${item["task_status_before"]}) — ${item["reason"]}`);
      } else {
        lines.push(`  ✗ ${item["project_name"]} (${item["project_id"]}) — ${item["reason"]}`);
      }
    }
    if (items.length > 20) lines.push(`  ... and ${items.length - 20} more`);
    lines.push("");
  } else {
    lines.push(`Nothing to ${actionKey}.`);
    lines.push("");
  }

  if (skippedCount > 0) {
    lines.push(`Skipped (${skippedCount}):`);
    for (const item of skipped.slice(0, 10)) {
      const id = (item["task_id"] ?? item["project_id"] ?? "?") as string;
      const name = (item["project_name"] ?? "") as string;
      lines.push(`  ~ ${name ? name + " " : ""}${id} — ${item["reason"]}`);
    }
    if (skipped.length > 10) lines.push(`  ... and ${skipped.length - 10} more`);
  }

  return lines.join("\n");
}

export function makeKwBulkCleanupTool(client: WorkerClient) {
  return {
    name: "kw_bulk_cleanup",
    description:
      "Bulk PM portfolio hygiene actions. Three modes: " +
      "'duplicate_tasks' — close duplicate dead unfinished tasks; " +
      "'stale_tasks' — cancel active tasks with no activity for N hours; " +
      "'dead_projects' — archive test/smoke/debug projects with no active work. " +
      "Use dry_run=true to preview without making changes.",
    parameters: Type.Object({
      mode: Type.Union([
        Type.Literal("duplicate_tasks"),
        Type.Literal("stale_tasks"),
        Type.Literal("dead_projects"),
      ], { description: "Cleanup mode: duplicate_tasks | stale_tasks | dead_projects" }),
      dry_run: Type.Optional(Type.Boolean({ description: "Preview without making changes (default: false)" })),
      project_id: Type.Optional(Type.String({ description: "Scope duplicate_tasks to one project" })),
      stale_hours: Type.Optional(Type.Number({ description: "Stale threshold in hours for stale_tasks (default: 4)" })),
    }),
    async execute(_id: string, params: unknown) {
      const parsed = parsePayload(params, ["mode"]);
      if (isPayloadError(parsed)) return payloadErrorResponse(parsed);

      const mode = parsed["mode"] as CleanupMode;
      const dryRun = (parsed["dry_run"] as boolean | undefined) ?? false;

      if (!MODE_ENDPOINT[mode]) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: `Unknown mode '${mode}'. Use: duplicate_tasks | stale_tasks | dead_projects` }, null, 2),
          }],
        };
      }

      const body: Record<string, unknown> = { dry_run: dryRun };
      if (mode === "duplicate_tasks" && parsed["project_id"]) body["project_id"] = parsed["project_id"];
      if (mode === "stale_tasks" && parsed["stale_hours"]) body["stale_hours"] = parsed["stale_hours"];

      const response = await client.post<Record<string, unknown>>(MODE_ENDPOINT[mode], body);
      if ("_http_error" in response) {
        const err = (response["error"] as Record<string, string>) ?? {};
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ ok: false, failure_reason: err["message"] ?? "failed", error_code: err["code"] }, null, 2),
          }],
        };
      }

      return { content: [{ type: "text", text: formatCleanupResult(mode, response) }] };
    },
  };
}
