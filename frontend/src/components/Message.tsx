import { memo, useState, Children, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import {
  Check,
  Code2,
  Copy,
  ExternalLink,
  File,
  FileText,
  Globe,
  Image as ImageIcon,
  Pencil,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import type { Attachment, Message as MessageType, WebSearchResult } from "../types";

function formatBytes(bytes: number): string {
  if (!bytes || isNaN(bytes)) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(att: Attachment) {
  if (att.is_image) return <ImageIcon size={14} />;
  const ext = att.filename.split(".").pop()?.toLowerCase() || "";
  if (["py", "js", "ts", "tsx", "jsx", "html", "css", "json", "rs", "go", "c", "cpp", "java", "sql", "sh"].includes(ext)) {
    return <Code2 size={14} />;
  }
  if (["pdf", "docx", "txt", "md", "csv"].includes(ext)) {
    return <FileText size={14} />;
  }
  return <File size={14} />;
}

function formatTime(isoString?: string): string {
  if (!isoString) return "";
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function CopyButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  return (
    <button
      title={label}
      aria-label={label}
      className="action-btn"
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
      {copied ? <Check size={14} /> : <Copy size={14} />}
      <span>{failed ? "Select text to copy" : copied ? "Copied" : label}</span>
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
  const time = formatTime(message.created_at);

  return (
    <article
      className={`message ${message.role}`}
      aria-label={assistant ? "Assistant response" : "Your message"}
    >
      <div className="message-heading">
        <div className="heading-left">
          <span className={assistant ? "avatar assistant-avatar" : "avatar user-avatar"}>
            {assistant ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
                <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
              </svg>
            ) : (
              "U"
            )}
          </span>
          <strong className="author-name">{assistant ? "Forma" : "You"}</strong>
          {assistant && message.model && (
            <span className="message-model">{message.model}</span>
          )}
        </div>
        {time && <span className="message-time">{time}</span>}
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
                {att.page_count && att.page_count > 1 ? ` · ${att.page_count} pages` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Render web search source cards for assistant messages */}
      {assistant && message.sources && message.sources.length > 0 && (
        <div className="message-sources">
          <div className="sources-header">
            <Globe size={13} />
            <span>Search Sources ({message.sources.length})</span>
          </div>
          <div className="sources-list">
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
        </div>
      )}

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
                    <button
                      type="button"
                      className="copy-code-btn"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(rawCode);
                        } catch {}
                      }}
                      title="Copy code"
                      aria-label="Copy code"
                    >
                      <Copy size={13} />
                      <span>Copy</span>
                    </button>
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
                <a href={href} target="_blank" rel="noopener noreferrer" className="markdown-link">
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
          <small className="status-note error">Response interrupted. You can retry below.</small>
        )}
      </div>

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
            className="action-btn"
            onClick={onRegenerate}
            title="Regenerate response"
            aria-label="Regenerate response"
          >
            <RotateCcw size={13} />
            <span>{message.status === "error" ? "Retry" : "Regenerate"}</span>
          </button>
        )}
      </div>
    </article>
  );
});
