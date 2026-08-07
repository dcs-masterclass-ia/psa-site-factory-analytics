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

module.exports = { callClaude };
