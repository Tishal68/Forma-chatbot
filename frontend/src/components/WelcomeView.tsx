import React, { useState } from "react";
import {
  BookOpen,
  Code2,
  FileText,
  Globe,
  Lightbulb,
  PenLine,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

interface SuggestionItem {
  icon: React.ElementType;
  title: string;
  detail: string;
  prompt: string;
  tag: string;
  webSearch?: boolean;
}

const defaultSuggestions: SuggestionItem[] = [
  {
    icon: Code2,
    title: "Write & debug code",
    detail: "Build something clean in Python, TS, Rust or Go",
    prompt: "Write a high-performance Python function with type hints and docstrings. Ask me what it should do.",
    tag: "Coding",
  },
  {
    icon: Globe,
    title: "Search the live web",
    detail: "Get up-to-date facts and cited sources",
    prompt: "What are the latest developments in AI models and technology this year?",
    tag: "Web Search",
    webSearch: true,
  },
  {
    icon: Sparkles,
    title: "Step-by-step reasoning",
    detail: "Tackle hard math, logic, and systems problems",
    prompt: "Walk me step-by-step through solving a complex analytical problem. Ask what challenge I have.",
    tag: "Reasoning",
  },
  {
    icon: FileText,
    title: "Analyze documents & data",
    detail: "Extract insights from PDFs, CSVs, DOCX, or code",
    prompt: "I want to analyze a document or data file with you. Ask me what to look for.",
    tag: "Documents",
  },
  {
    icon: PenLine,
    title: "Draft clear writing",
    detail: "Turn rough thoughts into engaging drafts",
    prompt: "Help me write a concise, compelling document. Ask about my target audience and main message.",
    tag: "Writing",
  },
  {
    icon: Lightbulb,
    title: "Brainstorm architecture",
    detail: "Explore trade-offs, schemas, and clean design",
    prompt: "Brainstorm software architecture with me. Ask what requirements and scale we need to design for.",
    tag: "Design",
  },
];

interface WelcomeViewProps {
  onSelectPrompt: (prompt: string, autoWebSearch?: boolean) => void;
}

export function WelcomeView({ onSelectPrompt }: WelcomeViewProps) {
  const [showMore, setShowMore] = useState(false);
  return (
    <section className="welcome">
      <div className="welcome-symbol">✳</div>
      <div className="eyebrow">YOUR THINKING SPACE</div>
      <h1>How can I help you today?</h1>
      <p>Ask a question, work with files, or create something new.</p>

      <div className="suggestions">
        {defaultSuggestions.slice(0, showMore ? defaultSuggestions.length : 4).map((s) => (
          <button
            key={s.title}
            type="button"
            className="suggestion-card"
            onClick={() => onSelectPrompt(s.prompt, s.webSearch)}
          >
            <div className="suggestion-card-header">
              <span className="suggestion-icon-wrap">
                <s.icon size={18} />
              </span>
              <span className="suggestion-tag">{s.tag}</span>
            </div>
            <strong>{s.title}</strong>
            <span className="suggestion-detail">{s.detail}</span>
            <span className="suggestion-arrow" aria-hidden="true">↗</span>
          </button>
        ))}
      </div>

      <button type="button" className="welcome-more" aria-expanded={showMore} onClick={() => setShowMore(!showMore)}>
        {showMore ? "Fewer ideas" : "More ideas"}
      </button>
      <div className="privacy-note">
        <ShieldCheck size={15} /> Chats are saved to this browser’s visitor session.
      </div>
    </section>
  );
}
