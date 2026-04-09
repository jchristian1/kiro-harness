/**
 * test-harness.ts — Standalone verification of parsePayload and tool execute paths.
 *
 * Run with: npx tsx src/test-harness.ts
 * (requires tsx: npm install -D tsx)
 *
 * This does NOT require OpenClaw or the worker to be running.
 * It verifies the parsing layer only.
 * For full end-to-end, run with worker running and real task IDs.
 */

import { parsePayload, isPayloadError } from "./parsePayload.js";

// ---------------------------------------------------------------------------
// Test parsePayload directly
// ---------------------------------------------------------------------------

function assert(label: string, condition: boolean) {
  console.log(`${condition ? "✓" : "✗"} ${label}`);
  if (!condition) process.exitCode = 1;
}

console.log("\n=== parsePayload unit tests ===\n");

// Case 1: slash-command envelope with valid JSON
{
  const envelope = { command: '{"name":"test","path":"/tmp","description":"desc"}', commandName: "henry_local_folder_analyze", skillName: "henry_local_folder_analyze" };
  const result = parsePayload(envelope, ["name", "path", "description"]);
  assert("slash-command envelope: parses correctly", !isPayloadError(result));
  assert("slash-command envelope: name field", !isPayloadError(result) && result["name"] === "test");
  assert("slash-command envelope: path field", !isPayloadError(result) && result["path"] === "/tmp");
}

// Case 2: direct tool call (already parsed object)
{
  const direct = { name: "test", path: "/tmp", description: "desc" };
  const result = parsePayload(direct, ["name", "path", "description"]);
  assert("direct tool call: parses correctly", !isPayloadError(result));
  assert("direct tool call: name field", !isPayloadError(result) && result["name"] === "test");
}

// Case 3: empty command string
{
  const envelope = { command: "   ", commandName: "x", skillName: "x" };
  const result = parsePayload(envelope, ["name"]);
  assert("empty command: returns EMPTY_PAYLOAD", isPayloadError(result) && result.error_code === "EMPTY_PAYLOAD");
}

// Case 4: invalid JSON
{
  const envelope = { command: "{bad json}", commandName: "x", skillName: "x" };
  const result = parsePayload(envelope, ["name"]);
  assert("invalid JSON: returns INVALID_JSON", isPayloadError(result) && result.error_code === "INVALID_JSON");
}

// Case 5: JSON array (not an object)
{
  const envelope = { command: '["a","b"]', commandName: "x", skillName: "x" };
  const result = parsePayload(envelope, ["name"]);
  assert("array payload: returns NOT_AN_OBJECT", isPayloadError(result) && result.error_code === "NOT_AN_OBJECT");
}

// Case 6: missing required field
{
  const envelope = { command: '{"name":"test"}', commandName: "x", skillName: "x" };
  const result = parsePayload(envelope, ["name", "path"]);
  assert("missing field: returns MISSING_FIELD", isPayloadError(result) && result.error_code === "MISSING_FIELD");
  assert("missing field: correct field name", isPayloadError(result) && result.missing_field === "path");
}

// Case 7: task_id envelope (status/approve tools)
{
  const envelope = { command: '{"task_id":"task_01ABC"}', commandName: "henry_task_status", skillName: "henry_task_status" };
  const result = parsePayload(envelope, ["task_id"]);
  assert("task_id envelope: parses correctly", !isPayloadError(result));
  assert("task_id envelope: task_id field", !isPayloadError(result) && result["task_id"] === "task_01ABC");
}

// Case 8: github_analyze envelope
{
  const envelope = { command: '{"name":"gh-test","repo_url":"https://github.com/org/repo","description":"analyze"}', commandName: "henry_github_analyze", skillName: "henry_github_analyze" };
  const result = parsePayload(envelope, ["name", "repo_url", "description"]);
  assert("github envelope: parses correctly", !isPayloadError(result));
  assert("github envelope: repo_url field", !isPayloadError(result) && result["repo_url"] === "https://github.com/org/repo");
}

// Case 9: new_project envelope
{
  const envelope = { command: '{"name":"new-test","source_url":"/tmp/ws","description":"build"}', commandName: "henry_new_project_analyze", skillName: "henry_new_project_analyze" };
  const result = parsePayload(envelope, ["name", "source_url", "description"]);
  assert("new_project envelope: parses correctly", !isPayloadError(result));
  assert("new_project envelope: source_url field", !isPayloadError(result) && result["source_url"] === "/tmp/ws");
}

// Case 10: direct object with error_code key (edge case — should NOT be treated as PayloadError)
{
  const direct = { name: "test", path: "/tmp", description: "desc", error_code: "something" };
  const result = parsePayload(direct, ["name", "path", "description"]);
  assert("object with error_code key: NOT treated as PayloadError", !isPayloadError(result));
}

console.log("\n=== All tests complete ===\n");
console.log("Next: run with real worker to verify HTTP path.");
console.log("  KIRO_WORKER_URL=http://localhost:4000 npx tsx src/test-harness.ts");
