import React from "react";
import { FormaMark } from "./FormaMark";
import {
  Menu,
  PanelLeft,
  Pencil,
  Plus,
  Settings,
  Sliders,
  Sparkles,
} from "lucide-react";
import { ModelDetail, ProviderInfo } from "../types";

interface HeaderProps {
  sidebar: boolean;
  onOpenSidebar: () => void;
  messagesCount: number;
  title: string;
  ready: boolean;
  provider: string;
  providers: ProviderInfo[];
  onProviderChange?: (provider: string) => void;
  model: string;
  models?: string[];
  modelDetails?: ModelDetail[];
  busy: boolean;
  onModelChange?: (model: string) => void;
  onSelectModel?: (provider: string, model: string) => void;
  onNewChat: () => void;
  onRename?: () => void;
  onOpenSettings?: (tab?: "general" | "memory" | "appearance" | "advanced") => void;
  theme?: string;
  onToggleTheme?: () => void;
  onExportChat?: () => void;
}

export function Header({
  sidebar,
  onOpenSidebar,
  messagesCount,
  title,
  provider,
  model,
  modelDetails = [],
  busy,
  onNewChat,
  onRename,
  onOpenSettings,
}: HeaderProps) {
  const displayTitle = messagesCount ? title : "Your thinking space";

  const isAuto =
    provider === "auto" ||
    model === "auto" ||
    (!provider && !model) ||
    model === "";
  const currentDetail = modelDetails.find((m) => m.id === model);

  // Accessible label for screen readers and regression tests
  const activeLabel = isAuto
    ? "Auto"
    : currentDetail
      ? `${currentDetail.name}`
      : model || "Choose model";

  return (
    <header className="topbar">
      <div className="header-left">
        {!sidebar && (
          <button
            className="icon-button menu-toggle-btn"
            aria-label="Open sidebar"
            onClick={onOpenSidebar}
            title="Open conversations sidebar (Ctrl + Shift + O)"
          >
            <Menu size={20} className="mobile-menu-icon" />
            <PanelLeft size={18} className="desktop-menu-icon" />
          </button>
        )}
        <div className="title-group desktop-title-group">
          <span className="header-title" title={displayTitle}>
            {displayTitle}
          </span>
          {messagesCount > 0 && onRename && (
            <button
              className="icon-button rename-title-btn"
              onClick={onRename}
              aria-label="Rename conversation"
              title="Rename conversation"
              disabled={busy}
            >
              <Pencil size={13} />
            </button>
          )}
        </div>
      </div>

      <div className="mobile-header-brand" aria-hidden="true">
        <FormaMark />
        <span className="brand-copy">
          <span>
            forma<span className="brand-dot">.</span>
          </span>
          <small className="brand-tagline">Think it. Shape it.</small>
        </span>
      </div>

      <div className="header-right">
        {/* Subtle, non-intrusive Forma Auto / active model indicator */}
        <button
          type="button"
          className={`forma-auto-pill ${!isAuto ? "manual" : ""}`}
          onClick={() => onOpenSettings?.("advanced")}
          aria-label={`Select model: currently ${activeLabel}`}
          title={
            isAuto
              ? "Forma Auto: Model selected automatically per request. Click for Advanced settings."
              : `Manual model: ${activeLabel}. Click for Advanced settings.`
          }
        >
          {isAuto ? (
            <>
              <Sparkles size={13} className="sparkle-icon" />
              <span className="forma-auto-pill-text">Forma Auto</span>
            </>
          ) : (
            <>
              <Sliders size={13} />
              <span className="forma-auto-pill-text">{activeLabel}</span>
            </>
          )}
        </button>

        {/* Normal chat actions */}
        <button
          type="button"
          className="icon-button header-action-btn"
          onClick={onNewChat}
          disabled={busy}
          aria-label="New chat"
          title="New chat (Ctrl + Shift + O)"
        >
          <Plus size={18} />
        </button>

        <button
          type="button"
          className="icon-button header-action-btn"
          onClick={() => onOpenSettings?.("general")}
          aria-label="Open settings"
          title="Settings"
        >
          <Settings size={18} />
        </button>
      </div>
    </header>
  );
}
