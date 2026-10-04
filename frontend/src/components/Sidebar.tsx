import React from "react";
import {
  MessageSquare,
  PanelLeftClose,
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
  connected,
  checking,
  ready,
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
          <span className="brand-mark">F</span>
          <span>
            forma<span className="brand-dot">.</span>
          </span>
          <button
            className="icon-button collapse"
            aria-label="Collapse sidebar"
            onClick={onClose}
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        <button className="new-chat" onClick={onNewChat} disabled={busy}>
          <Plus size={18} /> New chat <span title="Ctrl + Shift + O">↗</span>
        </button>

        <label className="search">
          <Search size={16} />
          <input
            aria-label="Search conversations"
            placeholder={chats.length > 0 ? `Search ${chats.length} conversations…` : "Search conversations…"}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          {search ? (
            <button
              className="clear-search"
              aria-label="Clear search"
              onClick={() => onSearchChange("")}
            >
              <X size={14} />
            </button>
          ) : chats.length > 0 ? (
            <span className="chat-count-tag" title={`${chats.length} saved chats`}>
              {chats.length}
            </span>
          ) : null}
        </label>

        <nav className="history">
          {chats.length === 0 ? (
            <div className="history-empty">
              <MessageSquare size={21} />
              <p>
                {search
                  ? "No conversations found"
                  : "Your conversations, organized."}
              </p>
              <small>
                {search
                  ? "Try a different search."
                  : "Start a chat. We’ll save it here automatically."}
              </small>
            </div>
          ) : (
            dateGroups.map((label) => {
              const rows = chats.filter((c) => groupDate(c.updated_at) === label);
              return rows.length ? (
                <section key={label}>
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
                      >
                        <MessageSquare size={15} />
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
          <button className="settings-button" onClick={onOpenSettings} title="Settings, guide & diagnostics">
            <Settings size={17} />
            <span>Settings</span>
            <span
              className={connected && ready ? "connection-dot" : "connection-dot offline"}
              title={ready ? "Connected & Ready" : "Setup needed"}
            />
          </button>
        </div>
      </aside>
    </>
  );
}
