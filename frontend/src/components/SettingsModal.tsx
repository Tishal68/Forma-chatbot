import React, { useEffect, useRef, useState } from "react";
import { ExternalLink, Eye, EyeOff, Key, RefreshCw, Sparkles, Trash2, X, Zap } from "lucide-react";
import { ModelDetail, ProviderInfo } from "../types";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  theme: string;
  onThemeChange: (theme: string) => void;
  provider: string;
  providers: ProviderInfo[];
  onProviderChange: (provider: string) => void;
  apiKey: string;
  onApiKeyChange: (key: string) => void;
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
  apiKey,
  onApiKeyChange,
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
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  const currentProviderInfo = providers.find((p) => p.id === provider);
  const currentModelDetail = modelDetails.find((m) => m.id === model);
  const isCloudProvider = provider !== "ollama";

  return (
    <dialog
      ref={dialogRef}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <div className="modal-header">
        <div>
          <h2>Workspace settings</h2>
          <p>Configure your AI provider, models, and appearance.</p>
        </div>
        <button
          className="icon-button"
          aria-label="Close settings"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>

      <label className="setting">
        AI Provider
        <select
          aria-label="AI Provider"
          disabled={busy}
          value={provider}
          onChange={(e) => onProviderChange(e.target.value)}
        >
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>

      {isCloudProvider && (
        <div className="setting api-key-setting">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}>
              <Key size={15} /> {currentProviderInfo?.name || "Provider"} API Key
            </span>
            {currentProviderInfo?.key_url && (
              <a
                href={currentProviderInfo.key_url}
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "4px", color: "var(--accent)" }}
              >
                Get API key <ExternalLink size={11} />
              </a>
            )}
          </div>
          <div style={{ display: "flex", gap: "8px", width: "100%", marginTop: "6px" }}>
            <input
              type={showKey ? "text" : "password"}
              aria-label="API Key"
              placeholder={`Paste your ${currentProviderInfo?.name || ""} API key…`}
              value={apiKey}
              onChange={(e) => onApiKeyChange(e.target.value)}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: "var(--text)",
                fontFamily: "monospace",
                fontSize: "13px",
              }}
            />
            <button
              type="button"
              className="quiet"
              onClick={() => setShowKey(!showKey)}
              title={showKey ? "Hide key" : "Show key"}
              style={{ padding: "8px 10px" }}
            >
              {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <small style={{ color: "var(--muted)", marginTop: "4px" }}>
            Stored locally in your browser. Never shared or exposed.
          </small>
        </div>
      )}

      <label className="setting">
        Model
        <select
          aria-label="Settings model"
          disabled={busy}
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
        >
          {!models.includes(model) && <option value={model}>{model}</option>}
          {models.map((m) => {
            const detail = modelDetails.find((d) => d.id === m);
            return (
              <option key={m} value={m}>
                {detail ? `${detail.name} ${detail.badge ? `(${detail.badge})` : ""}` : m}
              </option>
            );
          })}
        </select>
      </label>

      {currentModelDetail?.description && (
        <div style={{ margin: "-8px 0 12px", fontSize: "12px", color: "var(--muted)", padding: "0 2px" }}>
          <Sparkles size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }} />
          {currentModelDetail.description}
        </div>
      )}

      {provider === "ollama" && (
        <button className="quiet refresh-models" onClick={onRefreshModels}>
          <RefreshCw size={14} /> Refresh installed models
        </button>
      )}

      <label className="setting">
        Appearance
        <select
          aria-label="Theme"
          value={theme}
          onChange={(e) => onThemeChange(e.target.value)}
        >
          <option value="system">System</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </label>

      <label className="setting temperature">
        Creativity <output>{temperature.toFixed(1)}</output>
        <input
          aria-label="Temperature"
          type="range"
          min="0"
          max="2"
          step="0.1"
          value={temperature}
          onChange={(e) => onTemperatureChange(Number(e.target.value))}
        />
        <small>Lower for precision and code. Higher for creativity and brainstorming.</small>
      </label>

      <div className="danger-zone">
        <div>
          <strong>Clear all conversations</strong>
          <p>Permanently remove your chat history.</p>
        </div>
        <button
          disabled={busy}
          className="danger-button"
          onClick={onClearAll}
        >
          <Trash2 size={16} /> Clear
        </button>
      </div>
    </dialog>
  );
}
