import { memo, useState, Children, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import {
  Bot,
  Check,
  ChevronDown,
  Code2,
  Copy,
  ExternalLink,
  File,
  FileText,
  Globe,
  Image as ImageIcon,
  Pencil,
  RotateCcw,
  Terminal,
} from "lucide-react";
import type { Attachment, Message as MessageType } from "../types";

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

function CopyButton({
  text,
  label = "Copy",
  showLabel = false,
}: {
  text: string;
  label?: string;
  showLabel?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  return (
    <button
      title={failed ? "Failed" : copied ? "Copied" : label}
      aria-label={label}
      className={`action-btn ${showLabel ? "" : "icon-btn"}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        } catch {
          setFailed(true);
          setTimeout(() => setFailed(false), 2500);
        }
      }}
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {showLabel && <span>{failed ? "Failed" : copied ? "Copied" : label}</span>}
    </button>
  );
}

function plain(node: any): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(plain).join("");
  if (isValidElement(node)) return plain((node.props as any).children);
  return "";
}

export const Message = memo(function Message({
  message,
  last,
  busy,
  onRegenerate,
  onEdit,
}: {
  message: MessageType;
  last: boolean;
  busy: boolean;
  onRegenerate: () => void;
  onEdit: (message: MessageType) => void;
}) {
  const assistant = message.role === "assistant";
  const rawModelName = message.model
    ? message.model.split(":").slice(1).join(":")
    : "";

  return (
    <article
      className={`message ${message.role}`}
      aria-label={assistant ? "Assistant response" : "Your message"}
    >
      {assistant && (
        <div className="forma-avatar-wrap">
          <span className="forma-avatar" aria-hidden="true">
            f.
          </span>
        </div>
      )}
      <div className="message-content">
        <div className="message-header">
          {assistant ? (
            <strong className="author-name">Forma</strong>
          ) : (
            <strong className="author-name user-author-name">You</strong>
          )}
        </div>

      {/* Render attached files for user messages */}
      {!assistant && message.attachments && message.attachments.length > 0 && (
        <div className="message-attachments-list">
          {message.attachments.map((att) => (
            <div key={att.id} className="message-attachment-item">
              <span className="att-icon">{getFileIcon(att)}</span>
              <span className="att-name">{att.filename}</span>
              <span className="att-meta">
                {formatBytes(att.size_bytes)}
                {att.page_count && att.page_count > 1
                  ? ` · ${att.page_count} pages`
                  : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Generated image if present */}
      {assistant &&
        message.attachments
          ?.filter((a) => a.generated && a.is_image)
          .map((att) => {
            const url = `/api/conversations/${encodeURIComponent(att.conversation_id)}/attachments/${encodeURIComponent(att.id)}`;
            return (
              <figure className="generated-image" key={att.id}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Open generated image"
                >
                  <img src={url} alt="AI-generated image" loading="lazy" />
                </a>
                <figcaption>
                  <span>Generated with {rawModelName}</span>
                  <a href={`${url}/download`} download={att.filename}>
                    Download image
                  </a>
                </figcaption>
              </figure>
            );
          })}

      {/* Main markdown content */}
      <div className="message-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={{
            pre({ children }) {
              const child = Children.toArray(children)[0];
              const lang = isValidElement(child)
                ? ((child.props as any).className || "").match(
                    /language-(\S+)/,
                  )?.[1]
                : "";
              const rawCode = plain(children).replace(/\n$/, "");
              const lines = rawCode.split("\n");

              return (
                <div className="code-block">
                  <div className="code-toolbar">
                    <span className="code-lang">{lang || "code"}</span>
                    <CopyButton text={rawCode} label="Copy code" showLabel={true} />
                  </div>
                  <div className="code-content">
                    <div className="code-line-numbers" aria-hidden="true">
                      {lines.map((_, i) => (
                        <span key={i}>{i + 1}</span>
                      ))}
                    </div>
                    <pre>{children}</pre>
                  </div>
                </div>
              );
            },
            table({ children }) {
              return (
                <div className="table-scroll">
                  <table>{children}</table>
                </div>
              );
            },
            a({ children, href }) {
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="markdown-link"
                >
                  {children}
                </a>
              );
            },
          }}
        >
          {message.content}
        </ReactMarkdown>

        {assistant && message.status === "generating" && (
          <span className="dots" aria-label="Generating response">
            <i />
            <i />
            <i />
          </span>
        )}
        {assistant && message.status === "stopped" && (
          <small className="status-note stopped">Response stopped</small>
        )}
        {assistant && message.status === "error" && (
          <small className="status-note error">
            Generation interrupted. You can retry below.
          </small>
        )}
      </div>

      {/* Collapsed Agent Reasoning & Tools Disclosure */}
      {assistant && message.agent_steps && message.agent_steps.length > 0 && (
        <details className="agent-steps-disclosure">
          <summary className="agent-steps-summary">
            <div className="agent-summary-title">
              <Bot size={13} />
              <span>
                Agent Steps ({message.agent_steps.length}{" "}
                {message.agent_steps.length === 1 ? "step" : "steps"})
              </span>
            </div>
            <ChevronDown size={14} className="sources-caret" />
          </summary>
          <div className="agent-steps-content">
            {message.agent_steps.map((st, i) => (
              <div key={i} className="agent-step-item">
                <div className="agent-step-header">
                  <span className="agent-step-badge">Step {st.step}</span>
                  {st.tool && (
                    <span className="agent-step-tool">
                      <Terminal size={11} />
                      <span>{st.tool}</span>
                    </span>
                  )}
                </div>
                {st.thought && <p className="agent-step-thought">{st.thought}</p>}
                {st.output && (
                  <pre className="agent-step-output">
                    <code>
                      {typeof st.output === "string"
                        ? st.output
                        : JSON.stringify(st.output, null, 2)}
                    </code>
                  </pre>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Collapsed Sources Disclosure below assistant responses */}
      {assistant && message.sources && message.sources.length > 0 && (
        <details className="sources-disclosure">
          <summary className="sources-disclosure-summary">
            <div className="sources-summary-title">
              <Globe size={13} />
              <span>Sources ({message.sources.length})</span>
            </div>
            <ChevronDown size={14} className="sources-caret" />
          </summary>
          <div className="sources-disclosure-content">
            {message.sources.map((src, i) => {
              let domain = src.url;
              try {
                domain = new URL(src.url).hostname.replace(/^www\./, "");
              } catch {}
              return (
                <a
                  key={i}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-chip"
                  title={src.snippet || src.title}
                >
                  <span className="source-domain">{domain}</span>
                  <span className="source-title">{src.title}</span>
                  <ExternalLink size={11} className="source-ext" />
                </a>
              );
            })}
          </div>
        </details>
      )}

      {/* Message action controls below message */}
      <div className="message-actions">
        <CopyButton text={message.content} />
        {!assistant && (
          <button
            className="action-btn"
            onClick={() => onEdit(message)}
            title="Edit message"
            aria-label="Edit message"
            disabled={busy}
          >
            <Pencil size={13} />
            <span>Edit</span>
          </button>
        )}
        {assistant && last && !busy && (
          <button
            className="action-btn icon-btn"
            onClick={onRegenerate}
            title={
              message.status === "error"
                ? "Retry generation"
                : "Regenerate response"
            }
            aria-label={
              message.status === "error"
                ? "Retry generation"
                : "Regenerate response"
            }
          >
            <RotateCcw size={14} />
          </button>
        )}

        {/* Model attribution & progressive disclosure */}
        {assistant && message.model && (
          <div className="message-model-info">
            {message.auto_reason ? (
              <details className="routing-note">
                <summary>
                  <span className="routing-summary-label">
                    Auto · {message.auto_reason ? message.auto_reason.replace(/\.*$/, "") : "Best match for this request"}
                  </span>
                  <span className="why-link">Why this model?</span>
                </summary>
                <div className="routing-explanation">
                  <p>
                    <strong>Selected model:</strong>{" "}
                    <span className="message-model-name">{rawModelName}</span>
                  </p>
                  <p>{message.auto_reason}</p>
                </div>
              </details>
            ) : (
              <div className="manual-model-info">
                <details className="routing-note manual-note">
                  <summary>
                    <span className="routing-summary-label manual">
                      Manual model selection
                    </span>
                    <span className="why-link">Why this model?</span>
                  </summary>
                  <div className="routing-explanation">
                    <p>
                      <strong>Selected model:</strong>{" "}
                      <span className="message-model-name">{rawModelName}</span>
                    </p>
                    <p>Manually chosen in Settings.</p>
                  </div>
                </details>
              </div>
            )}
          </div>
        )}
      </div>
      </div>
    </article>
  );
});
