import React, { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Lock,
  Moon,
  RefreshCw,
  Sliders,
  Sparkles,
  Sun,
  Trash2,
  X,
} from "lucide-react";
import { ModelDetail, ProviderInfo } from "../types";

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
  busy: boolean;
  onRefreshModels: () => void;
  temperature: number;
  onTemperatureChange: (temp: number) => void;
  onClearAll: () => void;
}

export function SettingsModal({
  open,
  onClose,
  theme,
  onThemeChange,
  provider,
  providers,
  onProviderChange,
  model,
  models,
  modelDetails,
  onModelChange,
  busy,
  onRefreshModels,
  temperature,
  onTemperatureChange,
  onClearAll,
}: SettingsModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [activeTab, setActiveTab] = useState<"general" | "providers" | "guide" | "privacy">("general");

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  const currentProviderInfo = providers.find((p) => p.id === provider);

  return (
    <dialog
      ref={dialogRef}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
      className="settings-modal-dialog"
    >
      <div className="modal-header">
        <div>
          <h2>Settings</h2>
          <p>Manage model behavior, privacy, and preferences.</p>
        </div>
        <button
          className="icon-button"
          aria-label="Close settings"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>

      {/* Settings Navigation Tabs */}
      <div className="settings-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "general"}
          className={`settings-tab ${activeTab === "general" ? "active" : ""}`}
          onClick={() => setActiveTab("general")}
        >
          <Sliders size={15} />
          <span>General</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "providers"}
          className={`settings-tab ${activeTab === "providers" ? "active" : ""}`}
          onClick={() => setActiveTab("providers")}
        >
          <Sparkles size={15} />
          <span>Providers & Diagnostics</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "guide"}
          className={`settings-tab ${activeTab === "guide" ? "active" : ""}`}
          onClick={() => setActiveTab("guide")}
        >
          <BookOpen size={15} />
          <span>Quick Guide</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "privacy"}
          className={`settings-tab ${activeTab === "privacy" ? "active" : ""}`}
          onClick={() => setActiveTab("privacy")}
        >
          <Lock size={15} />
          <span>Privacy & Data</span>
        </button>
      </div>

      <div className="settings-tab-content">
        {/* Tab 1: General */}
        {activeTab === "general" && (
          <div className="tab-pane">
            <label className="setting">
              Appearance
              <select
                aria-label="Theme"
                value={theme}
                onChange={(e) => onThemeChange(e.target.value)}
              >
                <option value="system">System preference</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </label>

            <label className="setting temperature">
              Creativity / Temperature <output>{temperature.toFixed(1)}</output>
              <input
                aria-label="Temperature"
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={(e) => onTemperatureChange(Number(e.target.value))}
              />
              <small>Lower (0.0 – 0.4) for coding and factual queries. Higher (0.7 – 1.0) for brainstorming.</small>
            </label>

            <div className="keyboard-shortcuts-box">
              <h4>Keyboard Shortcuts</h4>
              <div className="shortcut-row">
                <span>New chat</span>
                <kbd>Ctrl + Shift + O</kbd>
              </div>
              <div className="shortcut-row">
                <span>Find in conversations</span>
                <kbd>Ctrl + K</kbd>
              </div>
              <div className="shortcut-row">
                <span>Send message</span>
                <kbd>Enter</kbd>
              </div>
              <div className="shortcut-row">
                <span>New line in composer</span>
                <kbd>Shift + Enter</kbd>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Providers & Diagnostics */}
        {activeTab === "providers" && (
          <div className="tab-pane">
            <div className="providers-list-container">
              {providers.map((p) => (
                <div key={p.id} className="provider-status-card">
                  <div className="provider-card-header">
                    <div>
                      <strong>{p.name}</strong>
                      {p.tagline && <span className="provider-card-tagline"> · {p.tagline}</span>}
                    </div>
                    {p.working ? (
                      <span className="provider-badge-ok">
                        <CheckCircle2 size={13} /> Active
                      </span>
                    ) : (
                      <span className="provider-badge-error">
                        <AlertTriangle size={13} /> {p.status || "Not configured"}
                      </span>
                    )}
                  </div>
                  {p.error && (
                    <div className="provider-error-detail">
                      {p.error}
                    </div>
                  )}
                  {p.models && p.models.length > 0 && (
                    <div className="provider-models-chips">
                      {p.models.map((m) => (
                        <span key={m.id} className="model-chip" title={m.description}>
                          {m.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div style={{ marginTop: "16px" }}>
              <button
                type="button"
                className="quiet refresh-models"
                onClick={onRefreshModels}
                disabled={busy}
                style={{ width: "100%", justifyContent: "center" }}
              >
                <RefreshCw size={14} /> Refresh connection & status
              </button>
            </div>
          </div>
        )}

        {/* Tab 3: Quick Guide */}
        {activeTab === "guide" && (
          <div className="tab-pane">
            <ol className="guide-steps">
              <li>
                <strong>Start with a question or task</strong>
                <p>
                  Type your prompt, attach files (PDF, DOCX, CSV, TXT, code, images), or toggle Web Search for live internet information.
                </p>
              </li>
              <li>
                <strong>Auto Smart Model Routing</strong>
                <p>
                  Forma automatically routes your prompt to the best configured model: vision-capable models for images, deep reasoning for coding/math, or fast conversational models for quick questions.
                </p>
              </li>
              <li>
                <strong>Follow up naturally</strong>
                <p>
                  Forma remembers context throughout the chat session. You can edit prior prompts or regenerate responses at any time.
                </p>
              </li>
            </ol>
          </div>
        )}

        {/* Tab 4: Privacy & Data */}
        {activeTab === "privacy" && (
          <div className="tab-pane">
            <div className="privacy-info-box">
              <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
                <Lock size={18} style={{ color: "var(--accent)", flexShrink: 0, marginTop: "2px" }} />
                <div>
                  <strong>Anonymous Visitor Isolation</strong>
                  <p style={{ margin: "4px 0 0", fontSize: "12px", color: "var(--muted)", lineHeight: "1.5" }}>
                    Your conversations, attachments, and searches are isolated under a secure, server-signed session cookie. No other visitor can access or view your chats. Clearing your cookies or site data resets this session.
                  </p>
                </div>
              </div>
            </div>

            <div className="danger-zone" style={{ marginTop: "24px" }}>
              <div>
                <strong>Clear all conversations</strong>
                <p>Permanently remove all chat history and uploaded files for this session.</p>
              </div>
              <button
                disabled={busy}
                className="danger-button"
                onClick={() => {
                  onClearAll();
                  onClose();
                }}
              >
                <Trash2 size={16} /> Clear all chats
              </button>
            </div>
          </div>
        )}
      </div>
    </dialog>
  );
}
