import React, { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, BookOpen, CheckCircle2, Database, Globe, Image as ImageIcon,
  Lock, Palette, RefreshCw, Settings, Sliders, Sparkles, Trash2, X,
} from "lucide-react";
import { ModelDetail, ProviderInfo } from "../types";
import { PersonalizationSettings } from "./PersonalizationSettings";

type Tab = "general" | "memory" | "appearance" | "advanced";
type Accent = "purple" | "blue" | "teal";

const navigation: { id: Tab; label: string; description: string; Icon: typeof Settings }[] = [
  { id: "general", label: "General", description: "Preferences, shortcuts & data", Icon: Settings },
  { id: "memory", label: "Chat & Memory", description: "Personalization and context", Icon: Database },
  { id: "appearance", label: "Appearance", description: "Theme and colours", Icon: Palette },
  { id: "advanced", label: "Advanced", description: "Models, providers & generation", Icon: Sliders },
];

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  theme: string;
  onThemeChange: (theme: string) => void;
  provider: string;
  providers: ProviderInfo[];
  onProviderChange: (provider: string) => void;
  model: string;
  models: string[];
  modelDetails: ModelDetail[];
  onModelChange: (model: string) => void;
  onSelectModel: (provider: string, model: string) => void;
  busy: boolean;
  onRefreshModels: () => void;
  temperature: number;
  onTemperatureChange: (temp: number) => void;
  onClearAll: () => void;
  webSearch: boolean;
  onWebSearchChange: (enabled: boolean) => void;
  imageMode: boolean;
}

function storedChoice(key: string, allowed: string[], fallback: string): string {
  try {
    const value = localStorage.getItem(key);
    return value && allowed.includes(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

export function SettingsModal({
  open, onClose, theme, onThemeChange, provider, providers, model, busy,
  onRefreshModels, temperature, onTemperatureChange, onClearAll,
  webSearch, onWebSearchChange, imageMode, onSelectModel,
}: SettingsModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [accent, setAccent] = useState<Accent>(() =>
    storedChoice("forma-accent", ["purple", "blue", "teal"], "purple") as Accent
  );
  const [animations, setAnimations] = useState(
    () => storedChoice("forma-animations", ["on", "off"], "on") === "on"
  );
  const [compact, setCompact] = useState(
    () => storedChoice("forma-density", ["comfortable", "compact"], "comfortable") === "compact"
  );

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => {
    document.documentElement.dataset.accent = accent;
    document.documentElement.dataset.motion = animations ? "on" : "off";
    document.documentElement.dataset.density = compact ? "compact" : "comfortable";
    try {
      localStorage.setItem("forma-accent", accent);
      localStorage.setItem("forma-animations", animations ? "on" : "off");
      localStorage.setItem("forma-density", compact ? "compact" : "comfortable");
    } catch {
      // Private browsing may block storage; the settings still work for this page.
    }
  }, [accent, animations, compact]);

  const active = navigation.find((entry) => entry.id === activeTab)!;
  return (
    <dialog
      ref={dialogRef}
      className="settings-modal-dialog"
      aria-label="Forma settings"
      onCancel={onClose}
      onClick={(event) => { if (event.target === dialogRef.current) onClose(); }}
    >
      <div className="modal-header">
        <div className="settings-heading">
          <Settings size={23} aria-hidden="true" />
          <div>
            <h2>Settings</h2>
            <p>Personalize your Forma experience.</p>
          </div>
        </div>
        <button type="button" className="icon-button" aria-label="Close settings" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="settings-layout">
        <nav className="settings-tabs" aria-label="Settings sections">
          {navigation.map(({ id, label, description, Icon }) => (
            <button
              key={id}
              type="button"
              className={`settings-tab ${activeTab === id ? "active" : ""}`}
              aria-current={activeTab === id ? "page" : undefined}
              onClick={() => setActiveTab(id)}
            >
              <Icon size={17} aria-hidden="true" />
              <span className="settings-tab-text">
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
            </button>
          ))}
        </nav>

        <section className="settings-tab-content" aria-label={active.label}>
          <div className="settings-section-title">
            <h3 className="settings-panel-heading">{active.label}</h3>
            <p>{active.description}</p>
          </div>

          {activeTab === "general" && (
            <div className="tab-pane">
              <div className="settings-panel-card">
                <h4>How Forma works</h4>
                <p>Forma Auto is the default mode, intelligently selecting the best available model for each request. You can configure manual overrides and provider connections in the Advanced tab.</p>
              </div>

              <div className="settings-panel-card settings-tool-row">
                <Globe size={19} aria-hidden="true" />
                <div>
                  <h4>Web search</h4>
                  <p>Use internet search for up-to-date information when enabled. Forma may also search automatically for changing facts. {imageMode && "Turn off image mode to enable web search."}</p>
                </div>
                <label className="settings-switch">
                  <input
                    type="checkbox"
                    aria-label="Enable web search for next messages"
                    checked={webSearch}
                    disabled={imageMode || busy}
                    onChange={(e) => onWebSearchChange(e.target.checked)}
                  />
                  <span aria-hidden="true" />
                </label>
              </div>

              <div className="settings-panel-card settings-tool-row">
                <ImageIcon size={19} aria-hidden="true" />
                <div>
                  <h4>Image generation</h4>
                  <p>{imageMode ? "Image mode is currently active." : "Enable image creation from the composer Tools menu when a supported provider is configured."}</p>
                </div>
              </div>

              <div className="settings-panel-card settings-tool-row">
                <BookOpen size={19} aria-hidden="true" />
                <div>
                  <h4>Document & file analysis</h4>
                  <p>Attach supported documents, code, or images using the + button in the composer for hybrid RAG indexing and reasoning.</p>
                </div>
              </div>

              <div className="keyboard-shortcuts-box">
                <h4>Keyboard shortcuts</h4>
                <div className="shortcut-row"><span>New chat</span><kbd>Ctrl + Shift + O</kbd></div>
                <div className="shortcut-row"><span>Search conversations</span><kbd>Ctrl + K</kbd></div>
                <div className="shortcut-row"><span>Send message</span><kbd>Enter</kbd></div>
                <div className="shortcut-row"><span>New line</span><kbd>Shift + Enter</kbd></div>
              </div>

              <div className="settings-panel-card">
                <h4><Lock size={16} aria-hidden="true" /> Browser session & privacy</h4>
                <p>Your conversations and preferences are associated with this browser session and do not sync across external devices. Clearing cookies or site data may reset your local session.</p>
              </div>

              <div className="danger-zone">
                <div>
                  <strong>Delete conversations and personalization</strong>
                  <p>Remove your chats, attachments, custom instructions, preferences, and memories for this session. This action cannot be undone.</p>
                </div>
                <button type="button" disabled={busy} className="danger-button" onClick={onClearAll}>
                  <Trash2 size={16} /> Delete all data
                </button>
              </div>

              <div className="settings-panel-card">
                <h4>About Forma</h4>
                <p>A personal AI assistant built with React, TypeScript, FastAPI, and SQLite. Designed for privacy, speed, and seamless multi-provider orchestration.</p>
                <a className="settings-about-link" href="https://github.com/Tishal68/Forma-chatbot" target="_blank" rel="noopener noreferrer">
                  View project on GitHub
                </a>
              </div>
            </div>
          )}

          {activeTab === "memory" && (
            <div className="tab-pane">
              {open && <PersonalizationSettings />}
            </div>
          )}

          {activeTab === "appearance" && (
            <div className="tab-pane">
              <div className="settings-panel-card">
                <h4>Theme</h4>
                <div className="settings-segmented" role="group" aria-label="Theme">
                  {(["dark", "light", "system"] as const).map((value) => (
                    <button
                      key={value}
                      type="button"
                      className={theme === value ? "active" : ""}
                      aria-pressed={theme === value}
                      onClick={() => onThemeChange(value)}
                    >
                      {value === "dark" ? "Dark" : value === "light" ? "Light" : "System"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="settings-panel-card">
                <h4>Accent colour</h4>
                <p>A subtle highlight for buttons, selected items, and focus states.</p>
                <div className="settings-colours" role="group" aria-label="Accent colour">
                  {(["purple", "blue", "teal"] as const).map((value) => (
                    <button
                      key={value}
                      type="button"
                      aria-label={value + " accent"}
                      aria-pressed={accent === value}
                      className={`accent-choice ${value} ${accent === value ? "selected" : ""}`}
                      onClick={() => setAccent(value)}
                    />
                  ))}
                </div>
              </div>

              <div className="settings-panel-card settings-preference-row">
                <div>
                  <h4>Compact spacing</h4>
                  <p>Fit more content on screen with tighter padding.</p>
                </div>
                <label className="settings-switch">
                  <input
                    type="checkbox"
                    checked={compact}
                    aria-label="Compact spacing"
                    onChange={(e) => setCompact(e.target.checked)}
                  />
                  <span aria-hidden="true" />
                </label>
              </div>

              <div className="settings-panel-card settings-preference-row">
                <div>
                  <h4>Interface animations</h4>
                  <p>Gentle transitions; system reduced-motion setting is always respected.</p>
                </div>
                <label className="settings-switch">
                  <input
                    type="checkbox"
                    checked={animations}
                    aria-label="Interface animations"
                    onChange={(e) => setAnimations(e.target.checked)}
                  />
                  <span aria-hidden="true" />
                </label>
              </div>
            </div>
          )}

          {activeTab === "advanced" && (
            <div className="tab-pane">
              <div className="settings-panel-card">
                <div className="settings-status-title">
                  <div>
                    <h4>Model selection</h4>
                    <p>Currently selected: <strong>{provider === "auto" || model === "auto" ? "Forma Auto" : model}</strong></p>
                  </div>
                  <Sparkles size={19} aria-hidden="true" />
                </div>
                <label className="setting">
                  <span>Selected model</span>
                  <select
                    aria-label="Selected model"
                    disabled={busy}
                    value={provider === "auto" || model === "auto" ? "auto" : JSON.stringify([provider, model])}
                    onChange={(event) => {
                      const value = event.target.value;
                      const [nextProvider, nextModel] = value === "auto" ? ["auto", "auto"] : JSON.parse(value);
                      onSelectModel(nextProvider, nextModel);
                    }}
                  >
                    <option value="auto">Forma Auto (recommended smart routing)</option>
                    {providers.map((p) => (
                      <optgroup key={p.id} label={p.name}>
                        {(p.models || []).map((m) => (
                          <option
                            key={m.id}
                            value={JSON.stringify([p.id, m.id])}
                            disabled={!p.working || (m.chat_compatible === false && !m.supports_image_generation)}
                          >
                            {m.name}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </label>
                <p>Forma Auto dynamically selects the best model per request based on task type, attachments, and provider health.</p>
              </div>

              <div className="settings-panel-card">
                <label className="setting temperature">
                  <span>Creativity / temperature <output>{temperature.toFixed(1)}</output></span>
                  <input
                    aria-label="Temperature"
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => onTemperatureChange(Number(e.target.value))}
                  />
                </label>
                <p>Lower values favour consistency and factual precision. Higher values introduce more creative variation.</p>
              </div>

              <div className="settings-panel-card">
                <h4>Provider connections & health</h4>
                <p>Active and configured model providers available to Forma.</p>
              </div>

              <div className="providers-list-container">
                {providers.map((p) => (
                  <div key={p.id} className="provider-status-card">
                    <div className="provider-card-header">
                      <div>
                        <strong>{p.name}</strong>
                        {p.tagline && <span className="provider-card-tagline"> · {p.tagline}</span>}
                      </div>
                      {p.working ? (
                        <span className="provider-badge-ok"><CheckCircle2 size={13} /> Available</span>
                      ) : (
                        <span className="provider-badge-error"><AlertTriangle size={13} /> {p.status || "Not configured"}</span>
                      )}
                    </div>
                    {p.error && <p className="provider-error-detail">{p.error}</p>}
                    {p.models && p.models.length > 0 && (
                      <div className="provider-models-chips">
                        {p.models.map((m) => (
                          <span key={m.id} className="model-chip" title={m.description}>{m.name}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <button type="button" className="quiet refresh-models" onClick={onRefreshModels} disabled={busy}>
                <RefreshCw size={15} /> Refresh connections
              </button>

              <div className="settings-panel-card">
                <h4>Model failover & safety</h4>
                <p>In Forma Auto mode, automatic failover reroutes to the next healthiest provider if rate limits, timeouts, or transient network errors occur.</p>
              </div>
            </div>
          )}
        </section>
      </div>
    </dialog>
  );
}
