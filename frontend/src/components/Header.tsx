import React from "react";
import { ChevronDown, PanelLeft, Plus } from "lucide-react";
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
}: HeaderProps) {
  return (
    <header className="topbar">
      <div>
        {!sidebar && (
          <button
            className="icon-button"
            aria-label="Open sidebar"
            onClick={onOpenSidebar}
          >
            <PanelLeft size={20} />
          </button>
        )}
        <span className="header-title">
          {messagesCount ? title : "Your thinking space"}
        </span>
      </div>
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
    </header>
  );
}
