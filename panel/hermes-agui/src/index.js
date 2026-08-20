import { createElement as h, ReactRef, useState, useRef, useCallback, useEffect } from "./react-shim.js";
// Acces paresseux : ne pas mettre en cache ReactRef.Fragment dans une const
// de module (window.React n'existe pas forcement encore a ce moment-la).
import { createRoot } from "./reactdom-shim.js";
import { HttpAgent, buildResumeArray } from "@ag-ui/client";

const TOOL_LABELS = {
  list_sites: "Sites",
  ask_agent_analytics: "Analytics",
  ask_agent_business: "Business",
  ask_agent_ux: "UX",
  get_series: "Données",
  show_chart: "Visualisation",
  ask_agent_dashboard: "Dashboard",
};

function useForceUpdate() {
  const [, setTick] = useState(0);
  return useCallback(() => setTick((t) => t + 1), []);
}

/** Rendu texte minimal (gras **..** + retours ligne), sans innerHTML. */
function renderInline(text, keyPrefix) {
  const parts = String(text || "").split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return h("strong", { key }, part.slice(2, -2));
    }
    return h(ReactRef.Fragment, { key }, part);
  });
}

function renderMarkdownish(text, keyPrefix) {
  const lines = String(text || "").split("\n");
  return lines.map((line, i) =>
    h(
      "div",
      { key: `${keyPrefix}-l${i}`, style: { minHeight: line ? undefined : "0.6em" } },
      renderInline(line, `${keyPrefix}-l${i}`)
    )
  );
}

function ToolPills({ toolCalls }) {
  if (!toolCalls || toolCalls.length === 0) return null;
  return h(
    "div",
    { style: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 } },
    toolCalls.map((tc) =>
      h(
        "span",
        {
          key: tc.id,
          style: {
            fontSize: 11,
            fontWeight: 700,
            background: "rgba(255,255,255,.1)",
            color: "#c9cfe6",
            borderRadius: 999,
            padding: "3px 10px",
          },
        },
        TOOL_LABELS[tc.function.name] || tc.function.name
      )
    )
  );
}

function MessageBubble({ message }) {
  if (message.role === "tool") return null;
  const isUser = message.role === "user";
  return h(
    "div",
    {
      style: {
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: 14,
      },
    },
    h(
      "div",
      {
        style: {
          maxWidth: "78%",
          background: isUser ? "#F5411E" : "rgba(255,255,255,.06)",
          color: isUser ? "#fff" : "#e8eaf5",
          borderRadius: 16,
          padding: "12px 16px",
          fontSize: 14.5,
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
        },
      },
      typeof message.content === "string" && message.content
        ? renderMarkdownish(message.content, message.id)
        : !isUser && (!message.toolCalls || message.toolCalls.length === 0)
        ? h("span", { style: { opacity: 0.5 } }, "…")
        : null,
      !isUser ? h(ToolPills, { toolCalls: message.toolCalls }) : null
    )
  );
}

function InterruptCard({ interrupts, onResolve, busy }) {
  if (!interrupts || interrupts.length === 0) return null;
  const first = interrupts[0];
  return h(
    "div",
    {
      style: {
        margin: "0 0 14px",
        background: "rgba(245,65,30,.12)",
        border: "1px solid rgba(245,65,30,.4)",
        borderRadius: 16,
        padding: "14px 16px",
      },
    },
    h("div", { style: { fontSize: 13.5, fontWeight: 700, color: "#ffb199", marginBottom: 4 } }, "Confirmation requise"),
    h("div", { style: { fontSize: 13.5, color: "#e8eaf5", lineHeight: 1.5, marginBottom: 12 } }, first.message || first.reason),
    h(
      "div",
      { style: { display: "flex", gap: 10 } },
      h(
        "button",
        {
          type: "button",
          disabled: busy,
          onClick: () => onResolve("resolved"),
          style: {
            border: "none",
            borderRadius: 999,
            padding: "9px 18px",
            background: "#F5411E",
            color: "#fff",
            fontWeight: 700,
            fontSize: 13,
            cursor: busy ? "default" : "pointer",
            opacity: busy ? 0.6 : 1,
          },
        },
        "Confirmer"
      ),
      h(
        "button",
        {
          type: "button",
          disabled: busy,
          onClick: () => onResolve("cancelled"),
          style: {
            border: "none",
            borderRadius: 999,
            padding: "9px 18px",
            background: "rgba(255,255,255,.1)",
            color: "#e8eaf5",
            fontWeight: 700,
            fontSize: 13,
            cursor: busy ? "default" : "pointer",
            opacity: busy ? 0.6 : 1,
          },
        },
        "Annuler"
      )
    )
  );
}

function HermesBetaPanel({ onClose }) {
  const agentRef = useRef(null);
  if (!agentRef.current) {
    agentRef.current = new HttpAgent({ url: "/api/agent?stream=1" });
  }
  const agent = agentRef.current;
  const forceUpdate = useForceUpdate();
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const listRef = useRef(null);

  useEffect(() => {
    const { unsubscribe } = agent.subscribe({
      onMessagesChanged: forceUpdate,
      onStateChanged: forceUpdate,
      onRunFinishedEvent: forceUpdate,
      onRunFailed: () => {
        setError("Une erreur est survenue. Réessaie.");
        forceUpdate();
      },
    });
    return unsubscribe;
  }, [agent, forceUpdate]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [agent.messages.length, agent.isRunning]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || agent.isRunning) return;
    setError(null);
    setInput("");
    agent.addMessage({ id: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()), role: "user", content: text });
    forceUpdate();
    try {
      await agent.runAgent();
    } catch (e) {
      console.error("[Hermes AG-UI]", e);
      setError("Une erreur est survenue. Réessaie.");
    }
  }, [agent, input, forceUpdate]);

  const resolveInterrupt = useCallback(
    async (status) => {
      const responses = {};
      for (const it of agent.pendingInterrupts) responses[it.id] = { status };
      const resume = buildResumeArray(agent.pendingInterrupts, responses);
      setError(null);
      try {
        await agent.runAgent({ resume });
      } catch (e) {
        console.error("[Hermes AG-UI]", e);
        setError("Une erreur est survenue. Réessaie.");
      }
    },
    [agent]
  );

  return h(
    ReactRef.Fragment,
    null,
    h(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "18px 22px",
          borderBottom: "1px solid rgba(255,255,255,.08)",
          flex: "none",
        },
      },
      h(
        "div",
        null,
        h("div", { style: { fontSize: 16, fontWeight: 800, color: "#fff" } }, "KamIA — Hermes (beta AG-UI)"),
        h(
          "div",
          { style: { fontSize: 12, fontWeight: 500, color: "#9aa0bd", marginTop: 2 } },
          "Réponses en streaming, confirmation avant modification du dashboard."
        )
      ),
      h(
        "button",
        {
          type: "button",
          onClick: onClose,
          style: {
            border: "none",
            background: "rgba(255,255,255,.08)",
            color: "#e8eaf5",
            width: 34,
            height: 34,
            borderRadius: "50%",
            cursor: "pointer",
            fontSize: 16,
          },
        },
        "×"
      )
    ),
    h(
      "div",
      { ref: listRef, style: { flex: 1, overflowY: "auto", padding: "20px 22px" } },
      agent.messages.length === 0
        ? h(
            "div",
            { style: { color: "#9aa0bd", fontSize: 13.5, textAlign: "center", marginTop: 40 } },
            "Pose une question sur le trafic, les leads ou la performance d'un site."
          )
        : agent.messages.map((m) => h(MessageBubble, { key: m.id, message: m })),
      h(InterruptCard, { interrupts: agent.pendingInterrupts, onResolve: resolveInterrupt, busy: agent.isRunning })
    ),
    error ? h("div", { style: { padding: "0 22px 10px", color: "#ff9f8f", fontSize: 12.5 } }, error) : null,
    h(
      "form",
      {
        style: { display: "flex", gap: 10, padding: "16px 22px", borderTop: "1px solid rgba(255,255,255,.08)", flex: "none" },
        onSubmit: (e) => {
          e.preventDefault();
          send();
        },
      },
      h("input", {
        type: "text",
        value: input,
        disabled: agent.isRunning || agent.pendingInterrupts.length > 0,
        onChange: (e) => setInput(e.target.value),
        placeholder: "Pose ta question…",
        style: {
          flex: 1,
          background: "rgba(255,255,255,.06)",
          border: "none",
          borderRadius: 14,
          padding: "0 16px",
          height: 46,
          color: "#fff",
          fontSize: 14.5,
          outline: "none",
        },
      }),
      h(
        "button",
        {
          type: "submit",
          disabled: agent.isRunning || agent.pendingInterrupts.length > 0,
          style: {
            border: "none",
            borderRadius: "50%",
            width: 46,
            height: 46,
            background: "#F5411E",
            color: "#fff",
            cursor: "pointer",
            flex: "none",
            opacity: agent.isRunning ? 0.6 : 1,
          },
        },
        "→"
      )
    )
  );
}

function createFab() {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "Hermes β";
  btn.setAttribute(
    "style",
    "position:fixed;right:24px;bottom:24px;z-index:9998;border:none;border-radius:999px;padding:0 20px;height:46px;background:#F5411E;color:#fff;font:700 13px/1 -apple-system,BlinkMacSystemFont,sans-serif;letter-spacing:.02em;cursor:pointer;box-shadow:0 14px 30px -10px rgba(245,65,30,.7)"
  );
  document.body.appendChild(btn);
  return btn;
}

function createOverlay() {
  const overlay = document.createElement("div");
  overlay.setAttribute(
    "style",
    "position:fixed;inset:0;z-index:9999;display:none;background:rgba(10,12,20,.55);align-items:center;justify-content:center;padding:24px;box-sizing:border-box"
  );
  const panel = document.createElement("div");
  panel.setAttribute(
    "style",
    "width:100%;max-width:760px;height:min(760px,92vh);background:#12162a;border-radius:24px;overflow:hidden;box-shadow:0 40px 100px -30px rgba(0,0,0,.6);display:flex;flex-direction:column;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"
  );
  overlay.appendChild(panel);
  document.body.appendChild(overlay);
  return { overlay, panel };
}

function init() {
  const fab = createFab();
  const { overlay, panel } = createOverlay();
  let root = null;

  const close = () => {
    overlay.style.display = "none";
  };
  const open = () => {
    overlay.style.display = "flex";
    if (!root) {
      root = createRoot(panel);
      root.render(h(HermesBetaPanel, { onClose: close }));
    }
  };

  fab.addEventListener("click", open);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
}

function waitForReact(cb) {
  if (window.React && window.ReactDOM) {
    cb();
    return;
  }
  const iv = setInterval(() => {
    if (window.React && window.ReactDOM) {
      clearInterval(iv);
      cb();
    }
  }, 60);
}

waitForReact(init);
