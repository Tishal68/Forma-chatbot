import React from "react";
import {
  CircleHelp,
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
  onOpenHelp: () => void;
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
  onOpenHelp,
}: SidebarProps) {
  const dateGroups = ["Today", "Yesterday", "Previous 7 days", "Older"];

  return (
    <>
      {sidebar && (
        <button
          className="drawer-scrim"
          aria-label="Close navigation"
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
            placeholder="Search conversations"
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
          <div className="local-note">
            <span
              className={
                connected ? "connection-dot" : "connection-dot offline"
              }
            />
            <div>
              <strong>
                {checking
                  ? "Checking connection…"
                  : ready
                    ? "Ready to chat"
                    : "Setup needed"}
              </strong>
              <small>Private workspace</small>
            </div>
          </div>
          <div style={{ fontSize: "11px", color: "var(--muted)", padding: "4px 8px 6px", lineHeight: "1.35", opacity: 0.85 }}>
            🔒 Chats are private to this browser session and may be lost if cookies are cleared.
          </div>
          <button className="settings-button" onClick={onOpenSettings}>
            <Settings size={17} /> Settings
          </button>
          <button className="settings-button" onClick={onOpenHelp}>
            <CircleHelp size={17} /> Quick guide
          </button>
        </div>
      </aside>
    </>
  );
}
