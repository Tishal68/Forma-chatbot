import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Conversation,
  Message as MessageType,
  api,
  deleteAttachment,
  streamChat,
  uploadAttachment,
} from "./services/api";
import { Message } from "./components/Message";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { WelcomeView } from "./components/WelcomeView";
import { Composer } from "./components/Composer";
import { SettingsModal } from "./components/SettingsModal";
import { QuickGuideModal } from "./components/QuickGuideModal";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { ModelDetail, ModelsResponse, ProviderInfo, QuestionPrompt } from "./types";

const localWorkspace = ["localhost", "127.0.0.1", "[::1]"].includes(
  window.location.hostname,
);

const defaultProviders: ProviderInfo[] = [
  { id: "groq", name: "Groq (Lightning Fast)", default_model: "llama-3.3-70b-versatile", key_url: "https://console.groq.com/keys" },
  { id: "openai", name: "OpenAI", default_model: "gpt-4o-mini", key_url: "https://platform.openai.com/api-keys" },
  { id: "gemini", name: "Google Gemini", default_model: "gemini-2.0-flash", key_url: "https://aistudio.google.com/app/apikey" },
  { id: "openrouter", name: "OpenRouter (All Models)", default_model: "meta-llama/llama-3.3-70b-instruct", key_url: "https://openrouter.ai/keys" },
  { id: "ollama", name: "Ollama (Local Offline)", default_model: "llama3.2", key_url: "https://ollama.com" },
];

export function App() {
  const [chats, setChats] = useState<Conversation[]>([]);
  const [id, setId] = useState<string | null>(
    localStorage.getItem("forma-active-chat"),
  );
  const [messages, setMessages] = useState<MessageType[]>([]);
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [sidebar, setSidebar] = useState(window.innerWidth > 800);
  const [settings, setSettings] = useState(false);

  // Multi-provider state
  const [provider, setProvider] = useState<string>(
    () => localStorage.getItem("forma-provider") || "openai",
  );
  const [providers, setProviders] = useState<ProviderInfo[]>(defaultProviders);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>(() => {
    try {
      return JSON.parse(localStorage.getItem("forma-api-keys") || "{}");
    } catch {
      return {};
    }
  });

  const [models, setModels] = useState<string[]>([]);
  const [modelDetails, setModelDetails] = useState<ModelDetail[]>([]);
  const [model, setModel] = useState<string>(
    localStorage.getItem(`forma-model-${provider}`) ||
      localStorage.getItem("forma-model") ||
      "",
  );

  const [theme, setTheme] = useState(
    localStorage.getItem("forma-theme") || "system",
  );
  const [temperature, setTemperature] = useState(() => {
    const saved = localStorage.getItem("forma-temperature");
    const num = saved ? Number(saved) : 0.7;
    return isNaN(num) ? 0.7 : Math.min(Math.max(num, 0), 2);
  });
  const [attachments, setAttachments] = useState<import("./types").Attachment[]>([]);
  const [webSearch, setWebSearch] = useState(() => {
    return localStorage.getItem("forma-web-search") === "true";
  });
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [connected, setConnected] = useState(false);
  const [checking, setChecking] = useState(true);
  const [help, setHelp] = useState(false);
  const [atBottom, setAtBottom] = useState(true);
  const [edit, setEdit] = useState<number | null>(null);

  const [question, setQuestion] = useState<QuestionPrompt | null>(null);

  function ask(title: string, value?: string): Promise<string | null> {
    return new Promise((resolve) => setQuestion({ title, value, resolve }));
  }

  function settle(value: string | null) {
    question?.resolve(value);
    setQuestion(null);
  }

  const controller = useRef<AbortController | null>(null);
  const locked = useRef(false);
  const scroll = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const loadVersion = useRef(0);
  const searchVersion = useRef(0);

  const currentProviderHasKey = Boolean(
    apiKeys[provider] || providers.find((p) => p.id === provider)?.has_key,
  );
  const ready =
    provider === "ollama"
      ? connected && models.includes(model)
      : currentProviderHasKey && models.length > 0;

  useEffect(() => {
    localStorage.setItem("forma-web-search", String(webSearch));
  }, [webSearch]);

  const refresh = useCallback(async () => {
    const version = ++searchVersion.current;
    try {
      const data = await api<Conversation[]>(
        "/conversations?q=" + encodeURIComponent(search),
      );
      if (version === searchVersion.current) setChats(data);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [search]);

  const loadModels = useCallback(
    async (targetProvider = provider, keyOverride = apiKeys[targetProvider]) => {
      setChecking(true);
      try {
        const query = new URLSearchParams({
          provider: targetProvider,
          ...(keyOverride ? { api_key: keyOverride } : {}),
        });
        const data = await api<ModelsResponse>("/models?" + query.toString());
        if (data.providers) setProviders(data.providers);
        setModels(data.models || []);
        setModelDetails(data.model_details || []);
        setConnected(true);

        setModel((old) => {
          const savedForProvider = localStorage.getItem(`forma-model-${targetProvider}`);
          const preferred = savedForProvider || old || data.default;
          if (data.models.includes(preferred)) return preferred;
          if (data.models.includes(preferred + ":latest")) return preferred + ":latest";
          return data.models[0] || data.default || "";
        });
      } catch {
        setConnected(false);
      } finally {
        setChecking(false);
      }
    },
    [provider, apiKeys],
  );

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    localStorage.setItem("forma-provider", newProvider);
    loadModels(newProvider, apiKeys[newProvider]);
  };

  const handleApiKeyChange = (key: string) => {
    const updated = { ...apiKeys, [provider]: key };
    setApiKeys(updated);
    localStorage.setItem("forma-api-keys", JSON.stringify(updated));
    loadModels(provider, key);
  };

  const handleAttachFiles = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    let cid = id;
    if (!cid) {
      try {
        const chat = await api<Conversation>("/conversations", { method: "POST" });
        cid = chat.id;
        setId(cid);
        refresh();
      } catch (e) {
        setError((e as Error).message || "Failed to initialize conversation for upload.");
        return;
      }
    }

    for (const file of fileArray) {
      const tempId = "temp-" + Math.random().toString(36).slice(2);
      const pending: import("./types").Attachment = {
        id: tempId,
        conversation_id: cid,
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        created_at: new Date().toISOString(),
        uploading: true,
        progress: 0,
        is_image: file.type.startsWith("image/"),
      };

      setAttachments((prev) => [...prev, pending]);

      try {
        const uploaded = await uploadAttachment(cid, file, (percent: number) => {
          setAttachments((prev) =>
            prev.map((a) => (a.id === tempId ? { ...a, progress: percent } : a)),
          );
        });
        setAttachments((prev) =>
          prev.map((a) => (a.id === tempId ? { ...uploaded, uploading: false } : a)),
        );
      } catch (e) {
        const errDetail = (e as Error).message || "Upload failed";
        setError(errDetail);
        setAttachments((prev) => prev.filter((a) => a.id !== tempId));
      }
    }
  };

  const handleRemoveAttachment = async (attachmentId: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
    if (id && !attachmentId.startsWith("temp-")) {
      try {
        await deleteAttachment(id, attachmentId);
      } catch {
        // Ignored
      }
    }
  };

  const open = useCallback(async (chat: Conversation) => {
    if (locked.current) return;
    const version = ++loadVersion.current;
    setLoading(true);
    setId(chat.id);
    setInput("");
    setAttachments([]);
    setEdit(null);
    setError("");
    if (window.innerWidth <= 800) setSidebar(false);
    try {
      const data = await api<Conversation>("/conversations/" + chat.id);
      if (version === loadVersion.current) {
        setMessages(data.messages || []);
        if (data.pending_attachments) {
          setAttachments(data.pending_attachments);
        }
        setAtBottom(true);
      }
    } catch (e) {
      setError((e as Error).message);
      if (version === loadVersion.current) {
        setId(null);
        setMessages([]);
        setAttachments([]);
      }
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, []);

  const newChat = useCallback(() => {
    if (locked.current) return;
    ++loadVersion.current;
    setLoading(false);
    setId(null);
    setMessages([]);
    setAttachments([]);
    setInput("");
    setEdit(null);
    setError("");
    setAtBottom(true);
    if (window.innerWidth <= 800) setSidebar(false);
    textarea.current?.focus();
  }, []);

  useEffect(() => {
    loadModels();
    const saved = localStorage.getItem("forma-active-chat");
    if (saved) open({ id: saved } as Conversation);
  }, [loadModels, open]);

  useEffect(() => {
    if (id) localStorage.setItem("forma-active-chat", id);
    else localStorage.removeItem("forma-active-chat");
  }, [id]);

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
      if (event.key === "Escape" && window.innerWidth <= 800) {
        setSidebar(false);
      }
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [newChat]);

  useEffect(() => {
    const timer = setTimeout(refresh, 180);
    return () => clearTimeout(timer);
  }, [refresh]);

  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.theme =
        theme === "system" ? (media.matches ? "dark" : "light") : theme;
    };
    apply();
    media.addEventListener("change", apply);
    localStorage.setItem("forma-theme", theme);
    return () => media.removeEventListener("change", apply);
  }, [theme]);

  useEffect(() => {
    if (model) {
      localStorage.setItem(`forma-model-${provider}`, model);
      localStorage.setItem("forma-model", model);
    }
  }, [model, provider]);

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
    if (messages.length > 0 && atBottom && scroll.current) {
      scroll.current.scrollTop = scroll.current.scrollHeight;
    }
  }, [messages, status, atBottom]);

  async function removeChat(chat: Conversation) {
    if (!(await ask("Delete “" + chat.title + "”? This cannot be undone."))) {
      return;
    }
    try {
      await api("/conversations/" + chat.id, { method: "DELETE" });
      if (id === chat.id) newChat();
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function renameChat(chat: Conversation) {
    const newTitle = await ask("Rename conversation", chat.title);
    if (!newTitle?.trim()) return;
    try {
      await api("/conversations/" + chat.id, {
        method: "PATCH",
        body: JSON.stringify({ title: newTitle }),
      });
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function send(regenerate = false) {
    if (!ready) {
      setSettings(true);
      return;
    }
    const canSend = regenerate || input.trim() || attachments.length > 0;
    if (locked.current || loading || !canSend) return;
    locked.current = true;
    setBusy(true);
    setError("");
    setStatus("Connecting to " + (providers.find((p) => p.id === provider)?.name || "model") + "…");
    setAtBottom(true);

    const content = input;
    const currentAttachments = [...attachments];
    const currentWebSearch = webSearch;
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
        const editIdx = edit !== null ? old.findIndex((m) => m.id === edit) : -1;
        const next =
          editIdx !== -1
            ? old.slice(0, editIdx)
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
                  attachments: currentAttachments,
                  web_search: currentWebSearch,
                },
              ]
            : []),
          {
            id: assistantId,
            role: "assistant",
            content: "",
            status: "generating",
            model: `${provider}:${model}`,
          },
        ];
      });

      setInput("");
      setAttachments([]);

      await streamChat(
        {
          conversation_id: cid,
          content,
          model,
          provider,
          api_key: apiKeys[provider] || undefined,
          temperature,
          regenerate,
          edit_message_id: edit,
          attachment_ids: currentAttachments.map((a) => a.id),
          web_search: currentWebSearch,
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
          if (event.type === "sources") {
            setMessages((old) =>
              old.map((m) =>
                m.id === assistantId ? { ...m, sources: event.sources } : m,
              ),
            );
          }
          if (event.type === "status") setStatus(event.message);
          if (event.type === "token") {
            accumulated += event.content;
            setStatus("");
            if (!frame) {
              frame = requestAnimationFrame(() => {
                setMessages((old) =>
                  old.map((m) =>
                    m.id === assistantId ? { ...m, content: accumulated } : m,
                  ),
                );
                frame = 0;
              });
            }
          }
          if (event.type === "error") setError(event.message);
        },
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError((e as Error).message || "Network interrupted. Try again.");
        if (!regenerate) {
          setInput(content);
          setAttachments(currentAttachments);
        }
      }
    } finally {
      if (frame) cancelAnimationFrame(frame);
      if (cid) {
        try {
          if (abort.signal.aborted) {
            await api("/conversations/" + cid + "/stop", { method: "POST" });
          }
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
      <Sidebar
        sidebar={sidebar}
        onClose={() => setSidebar(false)}
        busy={busy}
        onNewChat={newChat}
        search={search}
        onSearchChange={setSearch}
        chats={chats}
        activeId={id}
        onOpenChat={open}
        onRenameChat={renameChat}
        onDeleteChat={removeChat}
        connected={connected}
        checking={checking}
        ready={ready}
        onOpenSettings={() => setSettings(true)}
        onOpenHelp={() => setHelp(true)}
      />

      <main>
        <Header
          sidebar={sidebar}
          onOpenSidebar={() => setSidebar(true)}
          messagesCount={messages.length}
          title={title}
          ready={ready}
          model={model}
          models={models}
          modelDetails={modelDetails}
          busy={busy}
          onModelChange={setModel}
          onNewChat={newChat}
          onRename={() => {
            const chat = chats.find((c) => c.id === id);
            if (chat) renameChat(chat);
          }}
        />

        <div
          className="conversation-scroll"
          ref={scroll}
          onScroll={() => {
            const el = scroll.current;
            if (el) {
              setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 100);
            }
          }}
        >
          {loading ? (
            <div className="loading">Loading conversation…</div>
          ) : messages.length === 0 ? (
            <WelcomeView
              onSelectPrompt={(prompt) => {
                setInput(prompt);
                textarea.current?.focus();
              }}
            />
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

        <Composer
          ready={ready}
          checking={checking}
          connected={connected}
          localWorkspace={localWorkspace}
          onOpenHelp={() => setSettings(true)}
          onCheckConnection={() => loadModels()}
          atBottom={atBottom}
          messagesCount={messages.length}
          onScrollToBottom={() => {
            scroll.current?.scrollTo({
              top: scroll.current.scrollHeight,
              behavior: "smooth",
            });
            setAtBottom(true);
          }}
          error={error}
          onDismissError={() => setError("")}
          edit={edit}
          onCancelEdit={() => {
            setEdit(null);
            setInput("");
          }}
          input={input}
          onInputChange={setInput}
          loading={loading}
          busy={busy}
          onSend={() => send()}
          onStop={stop}
          textareaRef={textarea}
          attachments={attachments}
          onAttachFiles={handleAttachFiles}
          onRemoveAttachment={handleRemoveAttachment}
          webSearch={webSearch}
          onToggleWebSearch={() => setWebSearch(!webSearch)}
          onOpenSettings={() => setSettings(true)}
        />
      </main>

      <ConfirmDialog question={question} onSettle={settle} />

      <SettingsModal
        open={settings}
        onClose={() => setSettings(false)}
        theme={theme}
        onThemeChange={setTheme}
        provider={provider}
        providers={providers}
        onProviderChange={handleProviderChange}
        apiKey={apiKeys[provider] || ""}
        onApiKeyChange={handleApiKeyChange}
        model={model}
        models={models}
        modelDetails={modelDetails}
        onModelChange={setModel}
        busy={busy}
        onRefreshModels={() => loadModels()}
        temperature={temperature}
        onTemperatureChange={setTemperature}
        onClearAll={async () => {
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
      />

      <QuickGuideModal
        open={help}
        onClose={() => setHelp(false)}
        ready={ready}
        localWorkspace={localWorkspace}
        checking={checking}
        onCheckConnection={() => loadModels()}
      />
    </div>
  );
}
