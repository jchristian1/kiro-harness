import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createWorkerClient } from "./workerClient.js";
import { makeHenryLocalFolderAnalyzeTool } from "./tools/henryLocalFolderAnalyze.js";
import { makeHenryGithubAnalyzeTool } from "./tools/henryGithubAnalyze.js";
import { makeHenryNewProjectAnalyzeTool } from "./tools/henryNewProjectAnalyze.js";
import { makeHenryApproveImplementTool } from "./tools/henryApproveImplement.js";
import { makeHenryTaskStatusTool } from "./tools/henryTaskStatus.js";
import { makeHenryImplementTool } from "./tools/henryImplement.js";
import { makeKwCompleteTaskTool } from "./tools/kwCompleteTask.js";
import { makeKwCancelTaskTool } from "./tools/kwCancelTask.js";
import { makeKwListActiveTasksTool } from "./tools/kwListActiveTasks.js";
import { makeKwListActiveProjectsTool } from "./tools/kwListActiveProjects.js";
import { makeKwListPendingDecisionsTool } from "./tools/kwListPendingDecisions.js";
import { makeKwListUnfinishedTasksTool } from "./tools/kwListUnfinishedTasks.js";
import { makeKwGetProjectWorkspaceTool } from "./tools/kwGetProjectWorkspace.js";
import { makeKwListProjectContinuityTool } from "./tools/kwListProjectContinuity.js";
import { makeKwReinitializeProjectWorkspaceTool } from "./tools/kwReinitializeProjectWorkspace.js";

const DEFAULT_WORKER_URL = "http://localhost:4000";

export default definePluginEntry({
  id: "kw-worker-tools",
  name: "KW Worker Tools",
  description:
    "Deterministic kiro-worker tool operations for the Project Lead layer.",
  register(api) {
    // Read workerUrl from plugin config; fall back to localhost default.
    // Config path: plugins.entries["kw-worker-tools"].config.workerUrl
    const pluginConfig = api.pluginConfig as Record<string, unknown>;
    const workerUrl =
      typeof pluginConfig["workerUrl"] === "string"
        ? pluginConfig["workerUrl"]
        : DEFAULT_WORKER_URL;

    const client = createWorkerClient({ baseUrl: workerUrl });

    api.registerTool(makeHenryLocalFolderAnalyzeTool(client));
    api.registerTool(makeHenryGithubAnalyzeTool(client));
    api.registerTool(makeHenryNewProjectAnalyzeTool(client));
    api.registerTool(makeHenryApproveImplementTool(client));
    api.registerTool(makeHenryTaskStatusTool(client));
    api.registerTool(makeHenryImplementTool(client));
    api.registerTool(makeKwCompleteTaskTool(client));
    api.registerTool(makeKwCancelTaskTool(client));
    api.registerTool(makeKwListActiveTasksTool(client));
    api.registerTool(makeKwListActiveProjectsTool(client));
    api.registerTool(makeKwListPendingDecisionsTool(client));
    api.registerTool(makeKwListUnfinishedTasksTool(client));
    api.registerTool(makeKwGetProjectWorkspaceTool(client));
    api.registerTool(makeKwListProjectContinuityTool(client));
    api.registerTool(makeKwReinitializeProjectWorkspaceTool(client));
  },
});
