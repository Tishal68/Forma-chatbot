import React, { useEffect, useRef } from "react";
import { RefreshCw, X } from "lucide-react";

interface QuickGuideModalProps {
  open: boolean;
  onClose: () => void;
  ready: boolean;
  localWorkspace: boolean;
  checking: boolean;
  onCheckConnection: () => void;
}

export function QuickGuideModal({
  open,
  onClose,
  ready,
  localWorkspace,
  checking,
  onCheckConnection,
}: QuickGuideModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={onClose}
      aria-labelledby="guide-title"
    >
      <div className="modal-header">
        <div>
          <h2 id="guide-title">Welcome to Forma</h2>
          <p>A little help to get you started.</p>
        </div>
        <button
          className="icon-button"
          aria-label="Close quick guide"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>

      <ol className="guide-steps">
        <li>
          <strong>Start with a question</strong>
          <p>
            Type in the message box or choose a suggestion. Press Enter to send,
            or Shift + Enter for a new line.
          </p>
        </li>
        <li>
          <strong>Keep the conversation going</strong>
          <p>
            Ask follow-up questions naturally. Forma uses the context of your
            current chat.
          </p>
        </li>
        <li>
          <strong>Pick up where you left off</strong>
          <p>
            Chats save automatically and are kept strictly private to your browser
            session. If you clear your browser cookies or site data, your anonymous
            session will reset.
          </p>
        </li>
      </ol>

      <details className="setup-details" open={!ready}>
        <summary>Set up the AI connection</summary>
        {!localWorkspace && (
          <p>
            This hosted workspace needs an Ollama server configured by its owner.
            Set <code>OLLAMA_BASE_URL</code> and, if needed,{" "}
            <code>OLLAMA_API_KEY</code> in the hosting dashboard. Your personal
            computer’s Ollama is not connected automatically.
          </p>
        )}
        <p>
          Open Ollama on your computer. If you haven’t installed it, get it from{" "}
          <a
            href="https://ollama.com/download"
            target="_blank"
            rel="noreferrer"
          >
            ollama.com
          </a>
          .
        </p>
        <p>Download a model once in a terminal:</p>
        <code>ollama pull llama3.2</code>
        <p>
          Then use Settings → Refresh installed models. Your installed model is
          selected automatically.
        </p>
        <button
          className="guide-check"
          disabled={checking}
          onClick={onCheckConnection}
        >
          <RefreshCw size={15} />
          {checking
            ? "Checking…"
            : ready
              ? "Connected — check again"
              : "Check connection"}
        </button>
      </details>

      <div className="shortcut-help">
        <span>
          Find a chat <kbd>Ctrl K</kbd>
        </span>
        <span>
          New chat <kbd>Ctrl Shift O</kbd>
        </span>
      </div>
    </dialog>
  );
}
