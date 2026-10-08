import React from "react";
import { FormaMark } from "./FormaMark";
import {
  ChevronsLeft,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import { Conversation } from "../types";

interface SidebarProps {
  sidebar: boolean;
  onClose: () => void;
  busy: boolean;
  onNewChat: () => void;
  search: string;
  onSearchChange: (value: string) => void;
  chats: Conversation[];
  activeId: string | null;
  onOpenChat: (chat: Conversation) => void;
  onRenameChat: (chat: Conversation) => void;
  onDeleteChat: (chat: Conversation) => void;
  connected: boolean;
  checking: boolean;
  ready: boolean;
  onOpenSettings: () => void;
  onOpenHelp?: () => void;
}

function groupDate(dateStr: string): string {
  const d = new Date(dateStr);
  const today = new Date();
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

export function Sidebar({
  sidebar,
  onClose,
  busy,
  onNewChat,
  search,
  onSearchChange,
  chats,
  activeId,
  onOpenChat,
  onRenameChat,
  onDeleteChat,
  onOpenSettings,
}: SidebarProps) {
  const dateGroups = ["Today", "Yesterday", "Previous 7 days", "Older"];

  return (
    <>
      {sidebar && (
        <div
          className="drawer-scrim"
          role="presentation"
          aria-hidden="true"
          onClick={onClose}
        />
      )}
      <aside
        className={sidebar ? "sidebar visible" : "sidebar"}
        aria-label="Conversation navigation"
      >
        <div className="brand">
          <div className="brand-logo">
            <FormaMark />
            <span>forma<span className="brand-dot">.</span></span>
          </div>
          <button
            className="icon-button collapse"
            aria-label="Collapse sidebar"
            onClick={onClose}
            title="Collapse sidebar"
          >
            <ChevronsLeft size={18} />
          </button>
        </div>

        <button
          className="new-chat"
          onClick={onNewChat}
          disabled={busy}
          aria-label="Start new chat"
          title="New chat"
        >
          <Plus size={18} />
          <span>New chat</span>
        </button>

        <div className="sidebar-search-row">
        <div className="search">
          <Search size={15} />
          <input
            aria-label="Search conversations"
            placeholder="Search chats…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          {search && (
            <button
              className="clear-search"
              aria-label="Clear search"
              onClick={() => onSearchChange("")}
            >
              <X size={14} />
            </button>
          )}
        </div>
          <div className="sidebar-model-slot" id="sidebar-model-selector" aria-label="Model selection" />
        </div>

        <nav className="history" aria-label="Conversation history">
          {chats.length === 0 ? (
            <div className="history-empty">
              <MessageSquare size={20} />
              <p>{search ? "No conversations found" : "No chats yet"}</p>
              <small>
                {search
                  ? "Try a different search."
                  : "Your conversations will be saved here."}
              </small>
            </div>
          ) : (
            dateGroups.map((label) => {
              const rows = chats.filter((c) => groupDate(c.updated_at) === label);
              return rows.length ? (
                <section key={label} className="history-group">
                  <h2>{label}</h2>
                  {rows.map((c) => (
                    <div
                      key={c.id}
                      className={
                        "chat-row " + (activeId === c.id ? "selected" : "")
                      }
                    >
                      <button
                        className="chat-link"
                        disabled={busy}
                        onClick={() => onOpenChat(c)}
                        title={c.title}
                      >
                        <span>{c.title}</span>
                      </button>
                      <div className="chat-controls">
                        <button
                          title="Rename conversation"
                          aria-label={"Rename " + c.title}
                          onClick={() => onRenameChat(c)}
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          title="Delete conversation"
                          aria-label={"Delete " + c.title}
                          disabled={busy}
                          onClick={() => onDeleteChat(c)}
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
          <button
            className="settings-button"
            onClick={onOpenSettings}
            title="Settings & guide"
            aria-label="Settings"
          >
            <Settings size={16} />
            <span>Settings</span>
          </button>
        </div>
      </aside>
    </>
  );
}
