/**
 * Wrapper minimal autour de l'API Messages d'Anthropic, en fetch brut --
 * meme discipline zero-dependance que le reste du repo (cf. api/refresh.js).
 */

const API_URL = "https://api.anthropic.com/v1/messages";

async function callClaude({ model, system, messages, tools, toolChoice, thinking, effort, maxTokens }) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error("ANTHROPIC_API_KEY non configuree sur le serveur.");

  const body = {
    model,
    max_tokens: maxTokens || 4096,
    messages,
  };
  if (system) body.system = system;
  if (tools) body.tools = tools;
  if (toolChoice) body.tool_choice = toolChoice;
  if (thinking) body.thinking = thinking;
  if (effort) body.output_config = { effort };

  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(body),
  });

  const json = await resp.json();
  if (!resp.ok) {
    const msg = (json && json.error && json.error.message) || resp.statusText;
    throw new Error("Claude API : " + msg);
  }
  return json;
}

/**
 * Meme appel que callClaude mais en streaming (SSE cote Anthropic). Yield
 * des evenements incrementaux ("text-delta", "tool-call") au fil de la
 * reponse, puis un evenement final "message-complete" avec le contenu
 * complet reconstruit (memes types de blocks que la reponse non-streamee),
 * pour rester un drop-in remplacement du tour-a-tour tool-use existant.
 */
async function* callClaudeStream({ model, system, messages, tools, toolChoice, thinking, effort, maxTokens }) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error("ANTHROPIC_API_KEY non configuree sur le serveur.");

  const body = { model, max_tokens: maxTokens || 4096, messages, stream: true };
  if (system) body.system = system;
  if (tools) body.tools = tools;
  if (toolChoice) body.tool_choice = toolChoice;
  if (thinking) body.thinking = thinking;
  if (effort) body.output_config = { effort };

  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok || !resp.body) {
    let msg = resp.statusText;
    try {
      const json = await resp.json();
      msg = (json && json.error && json.error.message) || msg;
    } catch (_) {}
    throw new Error("Claude API : " + msg);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const blocks = [];
  let stopReason = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIdx;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      const dataLine = rawEvent.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const payload = JSON.parse(dataLine.slice(5).trim());

      if (payload.type === "content_block_start") {
        blocks[payload.index] =
          payload.content_block.type === "tool_use"
            ? { type: "tool_use", id: payload.content_block.id, name: payload.content_block.name, _json: "" }
            : { type: "text", text: "" };
      } else if (payload.type === "content_block_delta") {
        const block = blocks[payload.index];
        if (payload.delta.type === "text_delta") {
          block.text += payload.delta.text;
          yield { type: "text-delta", text: payload.delta.text };
        } else if (payload.delta.type === "input_json_delta") {
          block._json += payload.delta.partial_json;
        }
      } else if (payload.type === "content_block_stop") {
        const block = blocks[payload.index];
        if (block && block.type === "tool_use") {
          try {
            block.input = JSON.parse(block._json || "{}");
          } catch (_) {
            block.input = {};
          }
          delete block._json;
          yield { type: "tool-call", id: block.id, name: block.name, input: block.input };
        }
      } else if (payload.type === "message_delta") {
        if (payload.delta && payload.delta.stop_reason) stopReason = payload.delta.stop_reason;
      } else if (payload.type === "error") {
        throw new Error("Claude API (stream) : " + (payload.error && payload.error.message));
      }
    }
  }

  yield {
    type: "message-complete",
    content: blocks
      .filter(Boolean)
      .map((b) => (b.type === "tool_use" ? { type: "tool_use", id: b.id, name: b.name, input: b.input } : { type: "text", text: b.text })),
    stop_reason: stopReason,
  };
}

module.exports = { callClaude, callClaudeStream };
