import React from "react";
import { ChevronDown, PanelLeft, Pencil, Plus } from "lucide-react";
import { ModelDetail } from "../types";

interface HeaderProps {
  sidebar: boolean;
  onOpenSidebar: () => void;
  messagesCount: number;
  title: string;
  ready: boolean;
  model: string;
  models: string[];
  modelDetails?: ModelDetail[];
  busy: boolean;
  onModelChange: (model: string) => void;
  onNewChat: () => void;
  onRename?: () => void;
}

export function Header({
  sidebar,
  onOpenSidebar,
  messagesCount,
  title,
  ready,
  model,
  models,
  modelDetails = [],
  busy,
  onModelChange,
  onNewChat,
  onRename,
}: HeaderProps) {
  const displayTitle = messagesCount ? title : "Your thinking space";

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
        <div className="model-picker">
          <span className={ready ? "connection-dot" : "connection-dot offline"} />
          <select
            aria-label="Select model"
            value={model}
            disabled={busy}
            onChange={(e) => onModelChange(e.target.value)}
          >
            {!models.includes(model) && (
              <option value={model}>{model || "Choose a model"}</option>
            )}
            {models.map((m) => {
              const detail = modelDetails.find((d) => d.id === m);
              return (
                <option key={m} value={m}>
                  {detail ? `${detail.name}` : m}
                </option>
              );
            })}
          </select>
          <ChevronDown size={14} />
        </div>

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
      </div>
    </header>
  );
}
