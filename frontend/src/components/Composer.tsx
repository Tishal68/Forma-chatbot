import React, { useRef, useState } from "react";
import {
  ArrowDown,
  Code2,
  File,
  FileText,
  Globe,
  Image as ImageIcon,
  Loader2,
  Paperclip,
  Send,
  SlidersHorizontal,
  Square,
  X,
} from "lucide-react";
import { Attachment } from "../types";

interface ComposerProps {
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
  if (att.is_image) return <ImageIcon size={15} />;
  const ext = att.filename.split(".").pop()?.toLowerCase() || "";
  if (["py", "js", "ts", "tsx", "jsx", "html", "css", "json", "rs", "go", "c", "cpp", "java", "sql", "sh"].includes(ext)) {
    return <Code2 size={15} />;
  }
  if (["pdf", "docx", "txt", "md", "csv"].includes(ext)) {
    return <FileText size={15} />;
  }
  return <File size={15} />;
}

export function Composer({
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
  onOpenSettings,
}: ComposerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const hasUploading = attachments.some((a) => a.uploading);
  const canSend = (input.trim() || attachments.length > 0) && !loading && !busy && ready && !hasUploading;

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
      onAttachFiles(e.dataTransfer.files);
    }
  };

  return (
    <div className="composer-area">
      {!ready && (
        <div className="setup-notice" role="status">
          <div>
            <strong>
              {checking
                ? "Getting your workspace ready…"
                : connected
                  ? "Choose your first AI model"
                  : "Let’s connect your assistant"}
            </strong>
            <p>
              {checking
                ? "Checking your AI connection."
                : connected
                  ? "A one-time model download is needed before your first chat."
                  : localWorkspace
                    ? "Open Ollama on this computer, then check the connection."
                    : "Ask the workspace owner to check the AI server connection, then try again."}
            </p>
          </div>
          <button
            disabled={checking}
            onClick={connected ? onOpenHelp : onCheckConnection}
          >
            {checking
              ? "Checking…"
              : connected
                ? "Setup guide"
                : "Check again"}
          </button>
        </div>
      )}

      {!atBottom && messagesCount > 0 && (
        <button
          className="scroll-bottom"
          aria-label="Scroll to bottom"
          onClick={onScrollToBottom}
        >
          <ArrowDown size={18} />
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
            <X size={16} />
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
                title={att.error || `${att.filename} (${formatBytes(att.size_bytes)})`}
              >
                <span className="attachment-icon">{getFileIcon(att)}</span>
                <span className="attachment-name">{att.filename}</span>
                <span className="attachment-size">
                  {att.uploading
                    ? `${att.progress ?? 0}%`
                    : formatBytes(att.size_bytes)}
                </span>
                {att.uploading ? (
                  <Loader2 size={13} className="spin-icon" />
                ) : (
                  <button
                    type="button"
                    className="attachment-remove"
                    aria-label={`Remove ${att.filename}`}
                    onClick={() => onRemoveAttachment(att.id)}
                  >
                    <X size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        <textarea
          ref={textareaRef}
          aria-label="Message Forma"
          rows={1}
          placeholder={dragOver ? "Drop files to attach…" : "Message Forma…"}
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

        <div className="composer-bottom">
          <div className="composer-tools">
            <button
              type="button"
              className="tool-button"
              aria-label="Attach files (PDF, DOCX, CSV, TXT, Code, Images)"
              title="Attach files (PDF, DOCX, CSV, TXT, Code, Images)"
              onClick={() => fileInputRef.current?.click()}
            >
              <Paperclip size={18} />
            </button>

            <button
              type="button"
              className={`tool-button ${webSearch ? "active" : ""}`}
              aria-label={webSearch ? "Web search: Enabled (Click to disable)" : "Web search: Disabled (Click to enable)"}
              title={webSearch ? "Web search: ON (Real internet search)" : "Web search: OFF (Click to enable)"}
              onClick={onToggleWebSearch}
            >
              <Globe size={18} />
              {webSearch && <span className="active-dot" />}
            </button>

            <button
              type="button"
              className="tool-button"
              aria-label="Adjust parameters & settings"
              title="Parameters (Creativity, model, settings)"
              onClick={onOpenSettings}
            >
              <SlidersHorizontal size={18} />
            </button>
          </div>

          <div className="composer-actions">
            <span className="send-hint">
              <span>⌘</span> Enter to send
            </span>

            {busy ? (
              <button
                type="button"
                className="send stop"
                onClick={onStop}
                title="Stop generation"
                aria-label="Stop generation"
              >
                <Square size={15} fill="currentColor" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="submit"
                className="send primary-send"
                disabled={!canSend}
                title="Send message"
                aria-label="Send message"
              >
                <Send size={15} />
                <span>Send</span>
              </button>
            )}
          </div>
        </div>
      </form>

      <p className="composer-caption">
        AI can make mistakes. Check important information.
        <span>Enter to send · Shift + Enter for a new line</span>
      </p>
    </div>
  );
}
