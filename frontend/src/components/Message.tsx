import { memo, useState, Children, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Copy, Check, RotateCcw, Pencil } from "lucide-react";
import type { Message as MessageType } from "../services/api";

function CopyButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false),
    [failed, setFailed] = useState(false);
  return (
    <button
      title={label}
      aria-label={label}
      className="quiet"
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
      {copied ? <Check size={14} /> : <Copy size={14} />}{" "}
      {failed ? "Select text to copy" : copied ? "Copied" : label}
    </button>
  );
}
function plain(node: any): string {
  if (typeof node === "string") return node;
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
  return (
    <article
      className={"message " + message.role}
      aria-label={assistant ? "Assistant response" : "Your message"}
    >
      <div className="message-heading">
        <span className={assistant ? "avatar" : "avatar user-avatar"}>
          {assistant ? "F" : "Y"}
        </span>
        <strong>{assistant ? "Forma" : "You"}</strong>
        {assistant && message.model && (
          <span className="message-model">{message.model}</span>
        )}
      </div>
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
              return (
                <div className="code-block">
                  <div className="code-toolbar">
                    <span>{lang || "Code"}</span>
                    <CopyButton
                      text={plain(children).replace(/\n$/, "")}
                      label="Copy code"
                    />
                  </div>
                  <pre>{children}</pre>
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
                <a href={href} target="_blank" rel="noopener noreferrer">
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
          <small className="muted">Response stopped</small>
        )}
        {assistant && message.status === "error" && (
          <small className="muted">Response interrupted. Retry below.</small>
        )}
      </div>
      <div className="message-actions">
        <CopyButton text={message.content} />
        {assistant && last && !busy && (
          <button
            className="quiet"
            onClick={onRegenerate}
            title="Regenerate response"
            aria-label="Regenerate response"
          >
            <RotateCcw size={14} />{" "}
            {message.status === "error" ? "Retry" : "Regenerate"}
          </button>
        )}
        {!assistant && !busy && (
          <button
            className="quiet"
            onClick={() => onEdit(message)}
            title="Edit message"
          >
            <Pencil size={14} /> Edit
          </button>
        )}
      </div>
    </article>
  );
});
