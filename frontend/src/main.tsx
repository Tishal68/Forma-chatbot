import React, { useEffect, useRef, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUp,
  ArrowDown,
  Plus,
  Search,
  PanelLeftClose,
  PanelLeft,
  Settings,
  MessageSquare,
  Code2,
  BookOpen,
  Lightbulb,
  PenLine,
  FileText,
  Bug,
  X,
  Trash2,
  Pencil,
  Square,
  RefreshCw,
  ChevronDown,
  CircleHelp,
  ShieldCheck,
} from "lucide-react";
import {
  api,
  streamChat,
  Conversation,
  Message as MessageType,
} from "./services/api";
import { Message } from "./components/Message";
import "./styles.css";

const localWorkspace = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);

const suggestions = [
  {
    icon: BookOpen,
    title: "Explain a concept",
    detail: "Make the complex feel simple",
    prompt:
      "Help me understand a concept. Start by asking what I want to learn.",
  },
  {
    icon: Code2,
    title: "Write some code",
    detail: "Build something that works",
    prompt:
      "Help me write a program. Ask me about the language and what it should do.",
  },
  {
    icon: Bug,
    title: "Debug a problem",
    detail: "Find a fresh way forward",
    prompt: "Help me debug my program. I will share the code and the error.",
  },
  {
    icon: PenLine,
    title: "Find the right words",
    detail: "Turn a thought into a draft",
    prompt:
      "Help me write a clear, engaging draft. Ask about my audience and topic.",
  },
  {
    icon: Lightbulb,
    title: "Explore an idea",
    detail: "Give your next idea room",
    prompt: "Brainstorm ideas with me. Ask what challenge I am working on.",
  },
  {
    icon: FileText,
    title: "Help me study",
    detail: "Learn a little more deeply",
    prompt: "Help me study. Ask about my subject and create a learning plan.",
  },
];
function group(date: string) {
  const d = new Date(date),
    today = new Date();
  const delta = Math.floor(
    (new Date(today.toDateString()).getTime() -
      new Date(d.toDateString()).getTime()) /
      86400000,
  );
  return delta === 0
    ? "Today"
    : delta === 1
      ? "Yesterday"
      : delta < 7
        ? "Previous 7 days"
        : "Older";
}
function App() {
  const [chats, setChats] = useState<Conversation[]>([]),
    [id, setId] = useState<string | null>(
      localStorage.getItem("forma-active-chat"),
    ),
    [messages, setMessages] = useState<MessageType[]>([]),
    [input, setInput] = useState(""),
    [search, setSearch] = useState(""),
    [sidebar, setSidebar] = useState(innerWidth > 800),
    [settings, setSettings] = useState(false),
    [models, setModels] = useState<string[]>([]),
    [model, setModel] = useState(localStorage.getItem("forma-model") || ""),
    [theme, setTheme] = useState(
      localStorage.getItem("forma-theme") || "system",
    ),
    [temperature, setTemperature] = useState(
      Number(localStorage.getItem("forma-temperature") || 0.7),
    ),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [status, setStatus] = useState(""),
    [connected, setConnected] = useState(false),
    [checking, setChecking] = useState(true),
    [help, setHelp] = useState(false),
    [atBottom, setAtBottom] = useState(true),
    [edit, setEdit] = useState<number | null>(null);
  const [question, setQuestion] = useState<{
    title: string;
    value?: string;
    resolve: (value: string | null) => void;
  } | null>(null);
  const questionDialog = useRef<HTMLDialogElement>(null);
  const [answer, setAnswer] = useState("");
  function ask(title: string, value?: string): Promise<string | null> {
    setAnswer(value || "");
    return new Promise((resolve) => setQuestion({ title, value, resolve }));
  }
  function settle(value: string | null) {
    question?.resolve(value);
    setQuestion(null);
  }
  useEffect(() => {
    if (question) questionDialog.current?.showModal();
    else questionDialog.current?.close();
  }, [question]);
  const controller = useRef<AbortController | null>(null),
    locked = useRef(false),
    scroll = useRef<HTMLDivElement>(null),
    textarea = useRef<HTMLTextAreaElement>(null),
    dialog = useRef<HTMLDialogElement>(null),
    loadVersion = useRef(0),
    searchVersion = useRef(0);
  const helpDialog = useRef<HTMLDialogElement>(null);
  const ready = connected && models.includes(model);
  async function refresh() {
    const version = ++searchVersion.current;
    try {
      const data = await api<Conversation[]>(
        "/conversations?q=" + encodeURIComponent(search),
      );
      if (version === searchVersion.current) setChats(data);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function loadModels() {
    setChecking(true);
    try {
      const data = await api<{ models: string[]; default: string }>("/models");
      setModels(data.models);
      setConnected(true);
      setModel((old) => {
        const preferred = old || data.default;
        return data.models.includes(preferred)
          ? preferred
          : data.models.includes(preferred + ":latest")
            ? preferred + ":latest"
            : data.models[0] || "";
      });
    } catch (e) {
      setConnected(false);
    } finally {
      setChecking(false);
    }
  }
  useEffect(() => {
    loadModels();
    const saved = localStorage.getItem("forma-active-chat");
    if (saved) open({ id: saved } as Conversation);
  }, []);
  useEffect(() => {
    if (id) localStorage.setItem("forma-active-chat", id);
    else localStorage.removeItem("forma-active-chat");
  }, [id]);
  useEffect(() => {
    if (help) helpDialog.current?.showModal();
    else helpDialog.current?.close();
  }, [help]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if (
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key.toLowerCase() === "o"
      ) {
        event.preventDefault();
        newChat();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSidebar(true);
        requestAnimationFrame(() =>
          document.querySelector<HTMLInputElement>(".search input")?.focus(),
        );
      }
      if (event.key === "Escape" && innerWidth <= 800) setSidebar(false);
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, []);
  useEffect(() => {
    const timer = setTimeout(refresh, 180);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () =>
      (document.documentElement.dataset.theme =
        theme === "system" ? (media.matches ? "dark" : "light") : theme);
    apply();
    media.addEventListener("change", apply);
    localStorage.setItem("forma-theme", theme);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  useEffect(() => {
    localStorage.setItem("forma-model", model);
  }, [model]);
  useEffect(() => {
    localStorage.setItem("forma-temperature", String(temperature));
  }, [temperature]);
  useEffect(() => {
    if (textarea.current) {
      textarea.current.style.height = "auto";
      textarea.current.style.height =
        Math.min(textarea.current.scrollHeight, 180) + "px";
    }
  }, [input]);
  useEffect(() => {
    if (messages.length === 0 && scroll.current) scroll.current.scrollTop = 0;
    if (messages.length > 0 && atBottom && scroll.current)
      scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [messages, status]);
  useEffect(() => {
    if (settings) dialog.current?.showModal();
    else dialog.current?.close();
  }, [settings]);
  async function open(chat: Conversation) {
    if (locked.current) return;
    const version = ++loadVersion.current;
    setLoading(true);
    setId(chat.id);
    setInput("");
    setEdit(null);
    setError("");
    if (innerWidth <= 800) setSidebar(false);
    try {
      const data = await api<Conversation>("/conversations/" + chat.id);
      if (version === loadVersion.current) {
        setMessages(data.messages || []);
        setAtBottom(true);
      }
    } catch (e) {
      setError((e as Error).message);
      if (version === loadVersion.current) {
        setId(null);
        setMessages([]);
      }
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }
  function newChat() {
    if (locked.current) return;
    ++loadVersion.current;
    setLoading(false);
    setId(null);
    setMessages([]);
    setInput("");
    setEdit(null);
    setError("");
    setAtBottom(true);
    if (innerWidth <= 800) setSidebar(false);
    textarea.current?.focus();
  }
  async function remove(chat: Conversation) {
    if (!(await ask("Delete “" + chat.title + "”? This cannot be undone.")))
      return;
    try {
      await api("/conversations/" + chat.id, { method: "DELETE" });
      if (id === chat.id) newChat();
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function rename(chat: Conversation) {
    const title = await ask("Rename conversation", chat.title);
    if (!title?.trim()) return;
    try {
      await api("/conversations/" + chat.id, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function send(regenerate = false) {
    if (!ready) {
      setHelp(true);
      return;
    }
    if (locked.current || loading || (!regenerate && !input.trim())) return;
    locked.current = true;
    setBusy(true);
    setError("");
    setStatus("Connecting to your model…");
    setAtBottom(true);
    const content = input;
    let cid = id;
    const abort = new AbortController();
    controller.current = abort;
    let accumulated = "";
    let frame = 0;
    let assistantId = -Date.now();
    try {
      if (!cid) {
        const chat = await api<Conversation>("/conversations", {
          method: "POST",
        });
        cid = chat.id;
        setId(cid);
      }
      if (abort.signal.aborted) return;
      setMessages((old) => {
        let next =
          edit !== null
            ? old.slice(
                0,
                old.findIndex((m) => m.id === edit),
              )
            : regenerate && old.at(-1)?.role === "assistant"
              ? old.slice(0, -1)
              : old;
        return [
          ...next,
          ...(!regenerate
            ? [
                {
                  id: Date.now(),
                  role: "user" as const,
                  content,
                  status: "complete",
                },
              ]
            : []),
          {
            id: assistantId,
            role: "assistant",
            content: "",
            status: "generating",
            model,
          },
        ];
      });
      setInput("");
      await streamChat(
        {
          conversation_id: cid,
          content,
          model,
          temperature,
          regenerate,
          edit_message_id: edit,
        },
        abort.signal,
        (event) => {
          if (event.type === "start") {
            const oldId = assistantId;
            assistantId = event.message_id;
            setMessages((old) =>
              old.map((m) => (m.id === oldId ? { ...m, id: assistantId } : m)),
            );
            setStatus("Thinking…");
          }
          if (event.type === "status") setStatus(event.message);
          if (event.type === "token") {
            accumulated += event.content;
            setStatus("");
            if (!frame)
              frame = requestAnimationFrame(() => {
                setMessages((old) =>
                  old.map((m) =>
                    m.id === assistantId ? { ...m, content: accumulated } : m,
                  ),
                );
                frame = 0;
              });
          }
          if (event.type === "error") setError(event.message);
        },
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError((e as Error).message || "Network interrupted. Try again.");
        if (!regenerate) setInput(content);
      }
    } finally {
      if (frame) cancelAnimationFrame(frame);
      if (cid) {
        try {
          if (abort.signal.aborted)
            await api("/conversations/" + cid + "/stop", { method: "POST" });
          const data = await api<Conversation>("/conversations/" + cid);
          setMessages(data.messages || []);
        } catch {
          setMessages((old) =>
            old.map((m) =>
              m.id === assistantId
                ? { ...m, content: accumulated, status: "stopped" }
                : m,
            ),
          );
        }
      }
      setEdit(null);
      setBusy(false);
      locked.current = false;
      controller.current = null;
      setStatus("");
      refresh();
    }
  }
  async function stop() {
    controller.current?.abort();
    if (id) {
      try {
        await api("/conversations/" + id + "/stop", { method: "POST" });
      } catch (e) {
        setError((e as Error).message);
      }
    }
  }
  const sendRef = useRef(send);
  sendRef.current = send;
  const regenerateAction = useCallback(() => {
    sendRef.current(true);
  }, []);
  const editAction = useCallback(async (m: MessageType) => {
    if (
      await ask(
        "Edit this message? Replies after it will be replaced when you send.",
      )
    ) {
      setEdit(m.id);
      setInput(m.content);
      textarea.current?.focus();
    }
  }, []);
  const title = chats.find((c) => c.id === id)?.title || "New conversation";
  return (
    <div className={"app " + (!sidebar ? "collapsed" : "")}>
      {sidebar && (
        <button
          className="drawer-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside
        className={sidebar ? "sidebar visible" : "sidebar"}
        aria-label="Conversation navigation"
      >
        <div className="brand">
          <span className="brand-mark">F</span>
          <span>
            forma<span className="brand-dot">.</span>
          </span>
          <button
            className="icon-button collapse"
            aria-label="Collapse sidebar"
            onClick={() => setSidebar(false)}
          >
            <PanelLeftClose size={18} />
          </button>
        </div>
        <button className="new-chat" onClick={newChat} disabled={busy}>
          <Plus size={18} /> New chat <span title="Ctrl + Shift + O">↗</span>
        </button>
        <label className="search">
          <Search size={16} />
          <input
            aria-label="Search conversations"
            placeholder="Search conversations"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              className="clear-search"
              aria-label="Clear search"
              onClick={() => setSearch("")}
            >
              <X size={14} />
            </button>
          )}
        </label>
        <nav className="history">
          {chats.length === 0 ? (
            <div className="history-empty">
              <MessageSquare size={21} />
              <p>
                {search
                  ? "No conversations found"
                  : "Your conversations, organized."}
              </p>
              <small>
                {search
                  ? "Try a different search."
                  : "Start a chat. We’ll save it here automatically."}
              </small>
            </div>
          ) : (
            ["Today", "Yesterday", "Previous 7 days", "Older"].map((label) => {
              const rows = chats.filter((c) => group(c.updated_at) === label);
              return rows.length ? (
                <section key={label}>
                  <h2>{label}</h2>
                  {rows.map((c) => (
                    <div
                      key={c.id}
                      className={"chat-row " + (id === c.id ? "selected" : "")}
                    >
                      <button
                        className="chat-link"
                        disabled={busy}
                        onClick={() => open(c)}
                      >
                        <MessageSquare size={15} />
                        <span>{c.title}</span>
                      </button>
                      <div className="chat-controls">
                        <button
                          title="Rename conversation"
                          aria-label={"Rename " + c.title}
                          onClick={() => rename(c)}
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          title="Delete conversation"
                          aria-label={"Delete " + c.title}
                          disabled={busy}
                          onClick={() => remove(c)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </section>
              ) : null;
            })
          )}
        </nav>
        <div className="sidebar-footer">
          <div className="local-note">
            <span
              className={
                connected ? "connection-dot" : "connection-dot offline"
              }
            />
            <div>
              <strong>
                {checking
                  ? "Checking connection…"
                  : ready
                    ? "Ready to chat"
                    : "Setup needed"}
              </strong>
              <small>Private workspace · Ollama</small>
            </div>
          </div>
          <button className="settings-button" onClick={() => setSettings(true)}>
            <Settings size={17} /> Settings
          </button>
          <button className="settings-button" onClick={() => setHelp(true)}>
            <CircleHelp size={17} /> Quick guide
          </button>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            {!sidebar && (
              <button
                className="icon-button"
                aria-label="Open sidebar"
                onClick={() => setSidebar(true)}
              >
                <PanelLeft size={20} />
              </button>
            )}
            <span className="header-title">
              {messages.length ? title : "Your thinking space"}
            </span>
          </div>
          <div className="model-picker">
            <span
              className={ready ? "connection-dot" : "connection-dot offline"}
            />
            <select
              aria-label="Select model"
              value={model}
              disabled={busy}
              onChange={(e) => setModel(e.target.value)}
            >
              {!models.includes(model) && (
                <option value={model}>{model || "Choose a model"}</option>
              )}
              {models.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
            <ChevronDown size={14} />
          </div>
          <button
            className="header-new"
            onClick={newChat}
            disabled={busy}
            aria-label="Start new chat"
            title="New chat · Ctrl + Shift + O"
          >
            <Plus size={17} />
            <span>New chat</span>
          </button>
        </header>
        <div
          className="conversation-scroll"
          ref={scroll}
          onScroll={() => {
            const e = scroll.current!;
            setAtBottom(e.scrollHeight - e.scrollTop - e.clientHeight < 100);
          }}
        >
          {loading ? (
            <div className="loading">Loading conversation…</div>
          ) : messages.length === 0 ? (
            <section className="welcome">
              <div className="welcome-symbol">✳</div>
              <div className="eyebrow">YOUR EVERYDAY AI ASSISTANT</div>
              <h1>How can I help you today?</h1>
              <p>Write, learn, code, or plan — start with a question.</p>
              <div className="suggestions">
                {suggestions.map((s) => (
                  <button
                    key={s.title}
                    onClick={() => {
                      setInput(s.prompt);
                      textarea.current?.focus();
                    }}
                  >
                    <s.icon size={20} />
                    <strong>{s.title}</strong>
                    <span>{s.detail}</span>
                    <span className="suggestion-arrow">↗</span>
                  </button>
                ))}
              </div>
              <div className="privacy-note">
                <ShieldCheck size={15} /> Saved in your workspace. Ready when you are.
              </div>
            </section>
          ) : (
            <div className="messages">
              {messages.map((m, i) => (
                <Message
                  key={m.id}
                  message={m}
                  last={i === messages.length - 1}
                  busy={busy}
                  onRegenerate={regenerateAction}
                  onEdit={editAction}
                />
              ))}
              {busy && status && (
                <p className="generation-status" role="status">
                  {status}
                </p>
              )}
            </div>
          )}
        </div>
        <div className="composer-area">
          {!ready && (
            <div className="setup-notice" role="status">
              <div>
                <strong>
                  {checking
                    ? "Getting your workspace ready…"
                    : connected
                      ? "Choose your first AI model"
                      : "Let’s connect your assistant"}
                </strong>
                <p>
                  {checking
                    ? "Checking your AI connection."
                    : connected
                      ? "A one-time model download is needed before your first chat."
                      : localWorkspace ? "Open Ollama on this computer, then check the connection." : "Ask the workspace owner to check the AI server connection, then try again."}
                </p>
              </div>
              <button
                disabled={checking}
                onClick={connected ? () => setHelp(true) : loadModels}
              >
                {checking
                  ? "Checking…"
                  : connected
                    ? "Setup guide"
                    : "Check again"}
              </button>
            </div>
          )}
          {!atBottom && messages.length > 0 && (
            <button
              className="scroll-bottom"
              aria-label="Scroll to bottom"
              onClick={() => {
                scroll.current?.scrollTo({
                  top: scroll.current.scrollHeight,
                  behavior: "smooth",
                });
                setAtBottom(true);
              }}
            >
              <ArrowDown size={18} />
            </button>
          )}
          {error && (
            <div className="error" role="alert">
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {edit !== null && (
            <div className="edit-note">
              Editing an earlier message
              <button
                onClick={() => {
                  setEdit(null);
                  setInput("");
                }}
              >
                Cancel
              </button>
            </div>
          )}
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <textarea
              ref={textarea}
              aria-label="Message Forma"
              rows={1}
              placeholder="Message Forma…"
              value={input}
              disabled={loading}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <div className="composer-bottom">
              <span>
                <span className="mini-mark">✳</span>{" "}
                {busy
                  ? "Working on your answer…"
                  : "Your conversation is saved automatically"}
              </span>
              {busy ? (
                <button
                  type="button"
                  className="send stop"
                  onClick={stop}
                  title="Stop generation"
                  aria-label="Stop generation"
                >
                  <Square size={16} fill="currentColor" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  className="send"
                  disabled={!input.trim() || loading || !ready}
                  title="Send message"
                  aria-label="Send message"
                >
                  <span>Send</span>
                  <ArrowUp size={18} />
                </button>
              )}
            </div>
          </form>
          <p className="composer-caption">
            AI can make mistakes. Check important information.
            <span>Enter to send · Shift + Enter for a new line</span>
          </p>
        </div>
      </main>
      <dialog ref={questionDialog} onCancel={() => settle(null)}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            settle(question?.value !== undefined ? answer : "confirmed");
          }}
        >
          <h2 className="question-title">{question?.title}</h2>
          {question?.value !== undefined && (
            <input
              className="rename-input"
              aria-label="Conversation title"
              autoFocus
              maxLength={80}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
            />
          )}
          <div className="confirm-actions">
            <button type="button" onClick={() => settle(null)}>
              Cancel
            </button>
            <button type="submit" className="confirm-primary">
              {question?.value !== undefined ? "Save" : "Confirm"}
            </button>
          </div>
        </form>
      </dialog>
      <dialog
        ref={dialog}
        onCancel={() => setSettings(false)}
        onClick={(e) => {
          if (e.target === dialog.current) setSettings(false);
        }}
      >
        <div className="modal-header">
          <div>
            <h2>Workspace settings</h2>
            <p>Choose how Forma looks and responds.</p>
          </div>
          <button
            className="icon-button"
            aria-label="Close settings"
            onClick={() => setSettings(false)}
          >
            <X size={20} />
          </button>
        </div>
        <label className="setting">
          Appearance
          <select
            aria-label="Theme"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
          >
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>
        <label className="setting">
          Model
          <select
            aria-label="Settings model"
            disabled={busy}
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            {!models.includes(model) && <option value={model}>{model}</option>}
            {models.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
        <button className="quiet refresh-models" onClick={loadModels}>
          <RefreshCw size={14} /> Refresh installed models
        </button>
        <label className="setting temperature">
          Creativity <output>{temperature.toFixed(1)}</output>
          <input
            aria-label="Temperature"
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
          />
          <small>Lower for precision. Higher for exploration.</small>
        </label>
        <div className="danger-zone">
          <div>
            <strong>Clear all conversations</strong>
            <p>Permanently remove your chat history.</p>
          </div>
          <button
            disabled={busy}
            className="danger-button"
            onClick={async () => {
              if (!(await ask("Permanently delete ALL conversations?"))) return;
              try {
                await api("/conversations", { method: "DELETE" });
                newChat();
                refresh();
                setSettings(false);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <Trash2 size={16} /> Clear
          </button>
        </div>
      </dialog>
      <dialog
        ref={helpDialog}
        onCancel={() => setHelp(false)}
        aria-labelledby="guide-title"
      >
        <div className="modal-header">
          <div>
            <h2 id="guide-title">Welcome to Forma</h2>
            <p>A little help to get you started.</p>
          </div>
          <button
            className="icon-button"
            aria-label="Close quick guide"
            onClick={() => setHelp(false)}
          >
            <X size={20} />
          </button>
        </div>
        <ol className="guide-steps">
          <li>
            <strong>Start with a question</strong>
            <p>
              Type in the message box or choose a suggestion. Press Enter to
              send, or Shift + Enter for a new line.
            </p>
          </li>
          <li>
            <strong>Keep the conversation going</strong>
            <p>
              Ask follow-up questions naturally. Forma uses the context of your
              current chat.
            </p>
          </li>
          <li>
            <strong>Pick up where you left off</strong>
            <p>
              Chats save automatically. Use the sidebar to search, rename, or
              reopen them. Your last chat reopens on refresh.
            </p>
          </li>
        </ol>
        <details className="setup-details" open={!ready}>
          <summary>Set up the AI connection</summary>
          {!localWorkspace && <p>This hosted workspace needs an Ollama server configured by its owner. Set OLLAMA_BASE_URL and, if needed, OLLAMA_API_KEY in the hosting dashboard. Your personal computer’s Ollama is not connected automatically.</p>}
          <p>
            Open Ollama on your computer. If you haven’t installed it, get it
            from{" "}
            <a
              href="https://ollama.com/download"
              target="_blank"
              rel="noreferrer"
            >
              ollama.com
            </a>
            .
          </p>
          <p>Download a model once in a terminal:</p>
          <code>ollama pull llama3.2</code>
          <p>
            Then use Settings → Refresh installed models. Your installed model
            is selected automatically.
          </p>
          <button
            className="guide-check"
            disabled={checking}
            onClick={loadModels}
          >
            <RefreshCw size={15} />
            {checking
              ? "Checking…"
              : ready
                ? "Connected — check again"
                : "Check connection"}
          </button>
        </details>
        <div className="shortcut-help">
          <span>
            Find a chat <kbd>Ctrl K</kbd>
          </span>
          <span>
            New chat <kbd>Ctrl Shift O</kbd>
          </span>
        </div>
      </dialog>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
