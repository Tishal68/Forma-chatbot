import React, { useRef, useState, useEffect } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  ChevronDown,
  Code2,
  File,
  FileText,
  Globe,
  Image as ImageIcon,
  Loader2,
  Plus,
  Send,
  Square,
  X,
} from "lucide-react";
import { Attachment } from "../types";

interface ComposerProps {
  imageMode: boolean;
  imageHint: string;
  onToggleImageMode: () => void;
  ready: boolean;
  checking: boolean;
  connected: boolean;
  localWorkspace: boolean;
  onOpenHelp: () => void;
  onCheckConnection: () => void;
  atBottom: boolean;
  messagesCount: number;
  onScrollToBottom: () => void;
  error: string;
  onDismissError: () => void;
  edit: number | null;
  onCancelEdit: () => void;
  input: string;
  onInputChange: (value: string) => void;
  loading: boolean;
  busy: boolean;
  onSend: () => void;
  onStop: () => void;
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  attachments: Attachment[];
  onAttachFiles: (files: FileList | File[]) => void;
  onRemoveAttachment: (id: string) => void;
  webSearch: boolean;
  onToggleWebSearch: () => void;
  onOpenSettings: () => void;
}

function formatBytes(bytes: number): string {
  if (!bytes || isNaN(bytes)) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(att: Attachment) {
  if (att.is_image) return <ImageIcon size={14} />;
  const ext = att.filename.split(".").pop()?.toLowerCase() || "";
  if (
    [
      "py",
      "js",
      "ts",
      "tsx",
      "jsx",
      "html",
      "css",
      "json",
      "rs",
      "go",
      "c",
      "cpp",
      "java",
      "sql",
      "sh",
    ].includes(ext)
  ) {
    return <Code2 size={14} />;
  }
  if (["pdf", "docx", "txt", "md", "csv"].includes(ext)) {
    return <FileText size={14} />;
  }
  return <File size={14} />;
}

export function Composer({
  imageMode,
  imageHint,
  onToggleImageMode,
  ready,
  checking,
  connected,
  localWorkspace,
  onOpenHelp,
  onCheckConnection,
  atBottom,
  messagesCount,
  onScrollToBottom,
  error,
  onDismissError,
  edit,
  onCancelEdit,
  input,
  onInputChange,
  loading,
  busy,
  onSend,
  onStop,
  textareaRef,
  attachments,
  onAttachFiles,
  onRemoveAttachment,
  webSearch,
  onToggleWebSearch,
}: ComposerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toolsMenuRef = useRef<HTMLDivElement>(null);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  // Auto-resize textarea up to 160px
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      const newHeight = Math.min(el.scrollHeight, 160);
      el.style.height = `${Math.max(newHeight, 28)}px`;
    }
  }, [input, textareaRef]);

  // Close tools popover when clicking outside or pressing Escape
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        toolsMenuRef.current &&
        !toolsMenuRef.current.contains(e.target as Node)
      ) {
        setToolsOpen(false);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && toolsOpen) {
        setToolsOpen(false);
      }
    }
    if (toolsOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [toolsOpen]);

  const hasUploading = attachments.some((a) => a.uploading);
  const canSend =
    (input.trim() || attachments.length > 0) &&
    !loading &&
    !busy &&
    ready &&
    !hasUploading;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!dragOver) setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      if (!imageMode && !busy) onAttachFiles(e.dataTransfer.files);
    }
  };

  return (
    <div className="composer-area">
      {!ready && !imageMode && (
        <div className="setup-notice" role="status">
          <div>
            <strong>
              {checking
                ? "Checking server models…"
                : connected
                  ? "Choose your AI model"
                  : "Let’s connect your assistant"}
            </strong>
            <p>
              {checking
                ? "Connecting to configured AI providers."
                : connected
                  ? "Select a model or keep Auto to begin chatting."
                  : localWorkspace
                    ? "Start Ollama or configure a cloud provider key in backend environment."
                    : "Configure at least one AI provider in your deployment settings."}
            </p>
          </div>
          <button
            disabled={checking}
            onClick={connected ? onOpenHelp : onCheckConnection}
          >
            {checking ? "Checking…" : "Setup"}
          </button>
        </div>
      )}

      {!atBottom && messagesCount > 0 && (
        <button
          className="scroll-bottom"
          aria-label="Scroll to bottom"
          onClick={onScrollToBottom}
        >
          <ArrowDown size={17} />
        </button>
      )}

      {error && (
        <div className="error" role="alert">
          <span>{error}</span>
          <button
            className="icon-button"
            aria-label="Dismiss error"
            onClick={onDismissError}
          >
            <X size={15} />
          </button>
        </div>
      )}

      {edit !== null && (
        <div className="edit-note">
          Editing an earlier message
          <button onClick={onCancelEdit}>Cancel</button>
        </div>
      )}

      <form
        className={`composer ${dragOver ? "drag-over" : ""}`}
        onSubmit={(e) => {
          e.preventDefault();
          if (canSend) onSend();
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Hidden file input for attachment picker */}
        <input
          type="file"
          ref={fileInputRef}
          multiple
          style={{ display: "none" }}
          accept=".pdf,.docx,.txt,.md,.markdown,.csv,.py,.js,.ts,.tsx,.jsx,.html,.css,.json,.yaml,.yml,.sh,.c,.cpp,.h,.hpp,.rs,.go,.java,.rb,.php,.sql,.xml,.env,.log,.png,.jpg,.jpeg,.webp,.gif"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              onAttachFiles(e.target.files);
              e.target.value = "";
            }
          }}
        />

        {/* Attachment preview tray */}
        {attachments.length > 0 && (
          <div className="composer-attachments">
            {attachments.map((att) => (
              <div
                key={att.id}
                className={`attachment-chip ${att.uploading ? "uploading" : ""} ${att.error ? "has-error" : ""}`}
                title={
                  att.error || `${att.filename} (${formatBytes(att.size_bytes)})`
                }
              >
                <span className="attachment-icon">{getFileIcon(att)}</span>
                <span className="attachment-name">{att.filename}</span>
                <span className="attachment-size">
                  {att.uploading
                    ? `${att.progress ?? 0}%`
                    : formatBytes(att.size_bytes)}
                </span>
                {att.uploading ? (
                  <Loader2 size={12} className="spin-icon" />
                ) : (
                  <button
                    type="button"
                    className="attachment-remove"
                    aria-label={`Remove ${att.filename}`}
                    onClick={() => onRemoveAttachment(att.id)}
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Top row: Auto-growing Textarea */}
        <div className="composer-top-row">
          <textarea
            ref={textareaRef}
            aria-label="Message Forma"
            rows={1}
            placeholder={
              imageMode
                ? "Describe an image to create…"
                : dragOver
                  ? "Drop files to attach…"
                  : "Ask Forma anything…"
            }
            value={input}
            disabled={loading}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                if (canSend) onSend();
              }
            }}
          />
        </div>

        {/* Active mode chips row */}
        {(webSearch || imageMode) && (
          <div className="active-modes-row">
            {webSearch && (
              <button
                type="button"
                className="mode-chip"
                onClick={onToggleWebSearch}
                title="Web search enabled (click to remove)"
                aria-label="Web search enabled"
              >
                <Globe size={13} />
                <span>Web search</span>
                <X size={12} />
              </button>
            )}
            {imageMode && (
              <button
                type="button"
                className="mode-chip"
                onClick={onToggleImageMode}
                title="Create image mode enabled (click to remove)"
                aria-label="Create image mode"
                aria-pressed="true"
              >
                <ImageIcon size={13} />
                <span>Create image</span>
                <X size={12} />
              </button>
            )}
          </div>
        )}

        {imageHint && (
          <p className="image-mode-hint" role="status">
            {imageHint}
          </p>
        )}

        {/* Bottom row: Tools & Send */}
        <div className="composer-bottom">
          <div className="composer-tools">
            <button
              type="button"
              className="composer-btn attach-btn"
              aria-label="Attach files (PDF, DOCX, CSV, TXT, Code, Images)"
              title="Attach files"
              disabled={busy || imageMode}
              onClick={() => fileInputRef.current?.click()}
            >
              <Plus size={18} />
            </button>

            {/* Tools Menu Dropdown */}
            <div className="tools-dropdown" ref={toolsMenuRef}>
              <button
                type="button"
                className={`composer-btn tools-trigger ${toolsOpen ? "active" : ""}`}
                aria-label="Tools"
                aria-expanded={toolsOpen}
                onClick={() => setToolsOpen((prev) => !prev)}
                disabled={busy}
                title="Tools"
              >
                <span>Tools</span>
                <ChevronDown size={14} className="tools-caret" />
              </button>

              {toolsOpen && (
                <div className="tools-menu-popover">
                  <button
                    type="button"
                    className={`tools-menu-item ${webSearch ? "selected" : ""}`}
                    disabled={imageMode}
                    onClick={() => {
                      onToggleWebSearch();
                      setToolsOpen(false);
                    }}
                    aria-label="Web search"
                  >
                    <Globe size={15} />
                    <div className="tools-menu-info">
                      <strong>Web search</strong>
                      <span>Search real-time web sources</span>
                    </div>
                    {webSearch && <Check size={14} className="tools-check" />}
                  </button>

                  <button
                    type="button"
                    className={`tools-menu-item ${imageMode ? "selected" : ""}`}
                    disabled={attachments.length > 0}
                    onClick={() => {
                      onToggleImageMode();
                      setToolsOpen(false);
                    }}
                    aria-label="Create image mode"
                    aria-pressed={imageMode}
                  >
                    <ImageIcon size={15} />
                    <div className="tools-menu-info">
                      <strong>Create image</strong>
                      <span>Visualize ideas with AI</span>
                    </div>
                    {imageMode && <Check size={14} className="tools-check" />}
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="composer-actions">
            {busy ? (
              <button
                type="button"
                className="send-action-btn stop-action-btn"
                onClick={onStop}
                title="Stop generation"
                aria-label="Stop generation"
              >
                <Square size={14} fill="currentColor" />
              </button>
            ) : (
              <button
                type="submit"
                className={`send-action-btn submit-action-btn ${canSend ? "can-send" : ""}`}
                disabled={!canSend}
                title={
                  canSend
                    ? "Send message (Enter)"
                    : "Type a message or attach files"
                }
                aria-label="Send message"
              >
                <ArrowUpRight size={18} strokeWidth={2.4} />
              </button>
            )}
          </div>
        </div>
      </form>

      <p className="composer-caption">
        Forma can make mistakes. Check important information.
      </p>
    </div>
  );
}
