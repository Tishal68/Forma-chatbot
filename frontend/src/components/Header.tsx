import React, { useState, useRef, useEffect } from "react";
import { Check, ChevronDown, Eye, FileText, Globe, PanelLeft, Pencil, Plus, Sparkles, Zap } from "lucide-react";
import { ModelDetail, ProviderInfo } from "../types";

interface HeaderProps {
  sidebar: boolean;
  onOpenSidebar: () => void;
  messagesCount: number;
  title: string;
  ready: boolean;
  provider: string;
  providers: ProviderInfo[];
  onProviderChange: (provider: string) => void;
  model: string;
  models: string[];
  modelDetails?: ModelDetail[];
  busy: boolean;
  onModelChange: (model: string) => void;
  onSelectModel?: (provider: string, model: string) => void;
  onNewChat: () => void;
  onRename?: () => void;
}

export function Header({
  sidebar,
  onOpenSidebar,
  messagesCount,
  title,
  ready,
  provider,
  providers,
  onProviderChange,
  model,
  models,
  modelDetails = [],
  busy,
  onModelChange,
  onSelectModel,
  onNewChat,
  onRename,
}: HeaderProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const displayTitle = messagesCount ? title : "Your thinking space";

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [dropdownOpen]);

  const isAuto = provider === "auto" || model === "auto" || (!provider && !model) || model === "";
  const currentDetail = modelDetails.find((m) => m.id === model);
  const currentProvider = providers.find((p) => p.id === provider);

  // Label to show in selector button
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
            className="icon-button"
            aria-label="Open sidebar"
            onClick={onOpenSidebar}
          >
            <PanelLeft size={20} />
          </button>
        )}
        <div className="title-group">
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
              <Pencil size={14} />
            </button>
          )}
        </div>
      </div>

      <div className="header-right">
        {/* Unified Model & Provider Selector */}
        <div className="unified-selector" ref={dropdownRef}>
          <button
            type="button"
            className={`unified-selector-btn ${dropdownOpen ? "open" : ""}`}
            onClick={() => !busy && setDropdownOpen((prev) => !prev)}
            disabled={busy}
            aria-expanded={dropdownOpen}
            aria-label={`Select model: currently ${activeLabel}`}
            title={`Active: ${activeLabel} ${currentProvider ? `(${currentProvider.name})` : ""}`}
          >
            <span className={ready ? "connection-dot" : "connection-dot offline"} />
            {isAuto && <Sparkles size={13} className="auto-sparkle-icon" />}
            <span className="selected-model-name">{activeLabel}</span>
            {isAuto && <span className="auto-pill">Smart</span>}
            <ChevronDown size={14} className="selector-caret" />
          </button>

          {dropdownOpen && (
            <div className="unified-menu" role="menu">
              {/* Option: Auto Smart Routing */}
              <div
                className={`unified-menu-item auto-item ${isAuto ? "active" : ""}`}
                role="menuitem"
                tabIndex={0}
                onClick={() => {
                  if (onSelectModel) {
                    onSelectModel("auto", "auto");
                  } else {
                    onProviderChange("auto");
                    onModelChange("auto");
                  }
                  setDropdownOpen(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    if (onSelectModel) {
                      onSelectModel("auto", "auto");
                    } else {
                      onProviderChange("auto");
                      onModelChange("auto");
                    }
                    setDropdownOpen(false);
                  }
                }}
              >
                <div className="menu-item-left">
                  <div className="menu-item-title">
                    <Sparkles size={14} style={{ color: "var(--accent)" }} />
                    <strong>Auto (Smart Routing)</strong>
                    <span className="tag-badge default-badge">Recommended</span>
                  </div>
                  <div className="menu-item-desc">
                    Intelligently routes between vision, reasoning, web search, or fast chat based on your task.
                  </div>
                </div>
                {isAuto && <Check size={16} className="active-check" />}
              </div>

              <div className="unified-menu-divider" />

              {/* Grouped by Provider */}
              <div className="unified-menu-providers">
                {providers.map((p) => {
                  const pModels = p.models && p.models.length > 0
                    ? p.models
                    : (provider === p.id ? modelDetails : []);

                  return (
                    <div key={p.id} className="provider-group">
                      <div className="provider-group-header">
                        <span>{p.name}</span>
                        {!p.working && p.status && (
                          <span className="provider-status-tag">{p.status}</span>
                        )}
                      </div>
                      <div className="provider-model-list">
                        {pModels.map((m) => {
                          const isCurrentActive = !isAuto && provider === p.id && model === m.id;
                          return (
                            <div
                              key={m.id}
                              className={`unified-menu-item model-item ${isCurrentActive ? "active" : ""}`}
                              role="menuitem"
                              tabIndex={0}
                              onClick={() => {
                                if (onSelectModel) {
                                  onSelectModel(p.id, m.id);
                                } else {
                                  onProviderChange(p.id);
                                  onModelChange(m.id);
                                }
                                setDropdownOpen(false);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  if (onSelectModel) {
                                    onSelectModel(p.id, m.id);
                                  } else {
                                    onProviderChange(p.id);
                                    onModelChange(m.id);
                                  }
                                  setDropdownOpen(false);
                                }
                              }}
                            >
                              <div className="menu-item-left">
                                <div className="menu-item-title">
                                  <span>{m.name}</span>
                                  {m.badge && <span className="tag-badge">{m.badge}</span>}
                                  {/* Capability tags */}
                                  <div className="capability-tags">
                                    {m.supports_vision && (
                                      <span className="cap-tag vision" title="Supports image analysis">
                                        <Eye size={10} /> Vision
                                      </span>
                                    )}
                                    {m.supports_reasoning && (
                                      <span className="cap-tag reasoning" title="Specialized in deep reasoning & coding">
                                        <Sparkles size={10} /> Reasoning
                                      </span>
                                    )}
                                    {m.is_fast && (
                                      <span className="cap-tag fast" title="Ultra-low latency">
                                        <Zap size={10} /> Fast
                                      </span>
                                    )}
                                  </div>
                                </div>
                                {m.description && (
                                  <div className="menu-item-desc">{m.description}</div>
                                )}
                              </div>
                              {isCurrentActive && <Check size={16} className="active-check" />}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Header New Chat: Shown when sidebar is closed so users can always start a new chat */}
        {!sidebar && (
          <button
            className="header-new"
            onClick={onNewChat}
            disabled={busy}
            aria-label="Start new chat"
            title="New chat · Ctrl + Shift + O"
          >
            <Plus size={17} />
            <span>New chat</span>
          </button>
        )}
      </div>
    </header>
  );
}
