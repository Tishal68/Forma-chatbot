import React, { useEffect, useRef } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
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

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  const currentProviderInfo = providers.find((p) => p.id === provider);
  const currentModelDetail = modelDetails.find((m) => m.id === model);

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
          <p>Configure your active AI provider, model, and appearance.</p>
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
              {p.name} {p.working ? "● Ready" : `(⚠️ ${p.status || "Check server"})`}
            </option>
          ))}
        </select>
      </label>

      {currentProviderInfo && (
        <div style={{ margin: "-6px 0 14px", padding: "8px 12px", borderRadius: "6px", background: "var(--surface)", border: "1px solid var(--border)", fontSize: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
          {currentProviderInfo.working ? (
            <>
              <CheckCircle2 size={15} style={{ color: "var(--accent)", flexShrink: 0 }} />
              <span>
                <strong>{currentProviderInfo.name}</strong> is operational. Credentials are authenticated securely on the backend.
              </span>
            </>
          ) : (
            <>
              <AlertTriangle size={15} style={{ color: "#eab308", flexShrink: 0 }} />
              <span>
                <strong>{currentProviderInfo.name} status:</strong> {currentProviderInfo.error || "Provider reported an error. Please verify backend environment configuration."}
              </span>
            </>
          )}
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

      <div style={{ display: "flex", gap: "8px", marginBottom: "14px" }}>
        <button
          type="button"
          className="quiet refresh-models"
          onClick={onRefreshModels}
          disabled={busy}
          style={{ width: "100%", justifyContent: "center" }}
        >
          <RefreshCw size={14} /> Refresh provider & models
        </button>
      </div>

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
