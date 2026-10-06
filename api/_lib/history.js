/**
 * Validation de l'historique de conversation renvoye par le navigateur
 * (mode JSON de /api/agent). Le client le fabrique : on ne transmet a
 * Anthropic que des blocs de forme et de taille attendues (roles user /
 * assistant, types de blocs connus, bornes), jamais un objet arbitraire.
 */

const MAX_MESSAGES = 20;
const MAX_TEXT = 20000;
const MAX_TOOL_CONTENT = 100000;
const MAX_THINKING = 200000;
const MAX_ID = 128;
const MAX_B64_CHARS = Math.ceil((4 * 1024 * 1024) / 0.75); // 4 Mo decodes, comme les pieces jointes
const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);

const isStr = v => typeof v === "string";
const isObj = v => v && typeof v === "object" && !Array.isArray(v);

function cleanBlock(b) {
  if (!isObj(b)) return null;
  switch (b.type) {
    case "text":
      return isStr(b.text) && b.text ? { type: "text", text: b.text.slice(0, MAX_TEXT) } : null;
    case "thinking":
      return isStr(b.thinking) && isStr(b.signature) && b.thinking.length <= MAX_THINKING && b.signature.length <= 4096
        ? { type: "thinking", thinking: b.thinking, signature: b.signature } : null;
    case "redacted_thinking":
      return isStr(b.data) && b.data.length <= MAX_THINKING ? { type: "redacted_thinking", data: b.data } : null;
    case "tool_use":
      return isStr(b.id) && b.id.length <= MAX_ID && isStr(b.name) && b.name.length <= 64 && isObj(b.input)
        && JSON.stringify(b.input).length <= 50000
        ? { type: "tool_use", id: b.id, name: b.name, input: b.input } : null;
    case "tool_result": {
      if (!isStr(b.tool_use_id) || b.tool_use_id.length > MAX_ID) return null;
      let content;
      if (isStr(b.content)) content = b.content.slice(0, MAX_TOOL_CONTENT);
      else if (Array.isArray(b.content)) {
        content = b.content.map(x => (isObj(x) && x.type === "text" && isStr(x.text)) ? { type: "text", text: x.text.slice(0, MAX_TOOL_CONTENT) } : null).filter(Boolean);
      } else return null;
      const out = { type: "tool_result", tool_use_id: b.tool_use_id, content };
      if (b.is_error === true) out.is_error = true;
      return out;
    }
    case "image":
      return isObj(b.source) && b.source.type === "base64" && IMAGE_TYPES.has(b.source.media_type)
        && isStr(b.source.data) && b.source.data.length <= MAX_B64_CHARS
        ? { type: "image", source: { type: "base64", media_type: b.source.media_type, data: b.source.data } } : null;
    case "document":
      return isObj(b.source) && b.source.type === "base64" && b.source.media_type === "application/pdf"
        && isStr(b.source.data) && b.source.data.length <= MAX_B64_CHARS
        ? { type: "document", source: { type: "base64", media_type: "application/pdf", data: b.source.data } } : null;
    default:
      return null;
  }
}

function sanitizeHistory(history) {
  if (!Array.isArray(history)) return [];
  const out = [];
  for (const m of history.slice(-MAX_MESSAGES)) {
    if (!isObj(m) || (m.role !== "user" && m.role !== "assistant")) continue;
    let content;
    if (isStr(m.content)) content = m.content.slice(0, MAX_TEXT);
    else if (Array.isArray(m.content)) content = m.content.map(cleanBlock).filter(Boolean);
    else continue;
    if (!content.length) continue;
    out.push({ role: m.role, content });
  }
  // l'historique doit commencer par un vrai tour utilisateur (pas par un
  // tool_result orphelin dont le tool_use a ete coupe par la fenetre)
  while (out.length) {
    const first = out[0];
    const orphan = Array.isArray(first.content) && first.content[0] && first.content[0].type === "tool_result";
    if (first.role === "user" && !orphan) break;
    out.shift();
  }
  return out;
}

module.exports = { sanitizeHistory };
