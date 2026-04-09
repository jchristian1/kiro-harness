/**
 * parsePayload.ts — Coerce slash-command raw args or pre-parsed objects into
 * a validated plain object.
 *
 * When command-dispatch: tool + command-arg-mode: raw is used, OpenClaw calls
 * execute with:
 *   { command: "<raw json string>", commandName: "...", skillName: "..." }
 *
 * When called directly as a tool (e.g. by the model), execute receives the
 * already-parsed object matching the TypeBox schema.
 *
 * This helper handles both cases and returns a stable error shape on failure.
 */

export interface PayloadError {
  ok: false;
  step: "parse_payload";
  failure_reason: string;
  error_code: "EMPTY_PAYLOAD" | "INVALID_JSON" | "NOT_AN_OBJECT" | "MISSING_FIELD";
  missing_field?: string;
}

/**
 * Extract and parse the payload from whatever execute() receives.
 * Returns the parsed object or a PayloadError.
 *
 * Discrimination logic:
 * - If params has a string "command" key → slash-command envelope, parse command as JSON
 * - Otherwise → direct tool call, use params as-is
 */
export function parsePayload(
  raw: unknown,
  requiredFields: string[]
): Record<string, unknown> | PayloadError {
  let obj: unknown;

  // Case 1: slash-command dispatch — params is { command: "<json>", commandName, skillName }
  if (
    raw !== null &&
    typeof raw === "object" &&
    "command" in (raw as object) &&
    typeof (raw as Record<string, unknown>)["command"] === "string"
  ) {
    const commandStr = ((raw as Record<string, unknown>)["command"] as string).trim();
    if (!commandStr) {
      return {
        ok: false,
        step: "parse_payload",
        failure_reason: "Empty payload — provide a JSON object as the command argument.",
        error_code: "EMPTY_PAYLOAD",
      };
    }
    try {
      obj = JSON.parse(commandStr);
    } catch {
      return {
        ok: false,
        step: "parse_payload",
        failure_reason: `Invalid JSON: ${commandStr.slice(0, 120)}`,
        error_code: "INVALID_JSON",
      };
    }
  } else {
    // Case 2: direct tool call — params is already the object
    obj = raw;
  }

  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return {
      ok: false,
      step: "parse_payload",
      failure_reason: "Payload must be a JSON object, not a primitive or array.",
      error_code: "NOT_AN_OBJECT",
    };
  }

  const parsed = obj as Record<string, unknown>;

  for (const field of requiredFields) {
    if (!(field in parsed) || parsed[field] === undefined || parsed[field] === "") {
      return {
        ok: false,
        step: "parse_payload",
        failure_reason: `Missing required field: ${field}`,
        error_code: "MISSING_FIELD",
        missing_field: field,
      };
    }
  }

  return parsed;
}

/**
 * Type guard: returns true if the value is a PayloadError.
 * Uses step === "parse_payload" as the discriminator — safe because valid
 * parsed payloads will never have step set to this value.
 */
export function isPayloadError(
  val: Record<string, unknown> | PayloadError
): val is PayloadError {
  return (val as PayloadError).step === "parse_payload";
}

/** Wrap a PayloadError into the standard tool content response. */
export function payloadErrorResponse(err: PayloadError) {
  return {
    content: [{ type: "text", text: JSON.stringify(err, null, 2) }],
  };
}
