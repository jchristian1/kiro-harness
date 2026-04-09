import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createWorkerClient } from "./workerClient.js";
import { makeHenryLocalFolderAnalyzeTool } from "./tools/henryLocalFolderAnalyze.js";
import { makeHenryGithubAnalyzeTool } from "./tools/henryGithubAnalyze.js";
import { makeHenryNewProjectAnalyzeTool } from "./tools/henryNewProjectAnalyze.js";
import { makeHenryApproveImplementTool } from "./tools/henryApproveImplement.js";
import { makeHenryTaskStatusTool } from "./tools/henryTaskStatus.js";
import { makeHenryImplementTool } from "./tools/henryImplement.js";

const DEFAULT_WORKER_URL = "http://localhost:4000";

export default definePluginEntry({
  id: "henry-worker-tools",
  name: "Henry Worker Tools",
  description:
    "Deterministic kiro-worker tool operations for Henry Phase 1.5.",
  register(api) {
    // Read workerUrl from plugin config; fall back to localhost default.
    // Config path: plugins.entries["henry-worker-tools"].config.workerUrl
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
  },
});
