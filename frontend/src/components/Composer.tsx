import React from "react";
import { ArrowDown, ArrowUp, Square, X } from "lucide-react";

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
}: ComposerProps) {
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
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
      >
        <textarea
          ref={textareaRef}
          aria-label="Message Forma"
          rows={1}
          placeholder="Message Forma…"
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
              onSend();
            }
          }}
        />
        <div className="composer-bottom">
          <span>
            <span className="mini-mark">✳</span>{" "}
            {busy
              ? "Working on your answer…"
              : "Your conversation is saved automatically"}
          </span>
          {busy ? (
            <button
              type="button"
              className="send stop"
              onClick={onStop}
              title="Stop generation"
              aria-label="Stop generation"
            >
              <Square size={16} fill="currentColor" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              className="send"
              disabled={!input.trim() || loading || !ready}
              title="Send message"
              aria-label="Send message"
            >
              <span>Send</span>
              <ArrowUp size={18} />
            </button>
          )}
        </div>
      </form>
      <p className="composer-caption">
        AI can make mistakes. Check important information.
        <span>Enter to send · Shift + Enter for a new line</span>
      </p>
    </div>
  );
}
