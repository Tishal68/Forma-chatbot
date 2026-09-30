import React from "react";
import {
  BookOpen,
  Bug,
  Code2,
  FileText,
  Lightbulb,
  PenLine,
  ShieldCheck,
} from "lucide-react";
import { Suggestion } from "../types";

const defaultSuggestions: Suggestion[] = [
  {
    icon: BookOpen,
    title: "Explain a concept",
    detail: "Make the complex feel simple",
    prompt: "Help me understand a concept. Start by asking what I want to learn.",
  },
  {
    icon: Code2,
    title: "Write some code",
    detail: "Build something that works",
    prompt: "Help me write a program. Ask me about the language and what it should do.",
  },
  {
    icon: Bug,
    title: "Debug a problem",
    detail: "Find a fresh way forward",
    prompt: "Help me debug my program. I will share the code and the error.",
  },
  {
    icon: PenLine,
    title: "Find the right words",
    detail: "Turn a thought into a draft",
    prompt: "Help me write a clear, engaging draft. Ask about my audience and topic.",
  },
  {
    icon: Lightbulb,
    title: "Explore an idea",
    detail: "Give your next idea room",
    prompt: "Brainstorm ideas with me. Ask what challenge I am working on.",
  },
  {
    icon: FileText,
    title: "Help me study",
    detail: "Learn a little more deeply",
    prompt: "Help me study. Ask about my subject and create a learning plan.",
  },
];

interface WelcomeViewProps {
  onSelectPrompt: (prompt: string) => void;
}

export function WelcomeView({ onSelectPrompt }: WelcomeViewProps) {
  return (
    <section className="welcome">
      <div className="welcome-symbol">✳</div>
      <div className="eyebrow">YOUR EVERYDAY AI ASSISTANT</div>
      <h1>How can I help you today?</h1>
      <p>Write, learn, code, or plan — start with a question.</p>
      <div className="suggestions">
        {defaultSuggestions.map((s) => (
          <button
            key={s.title}
            onClick={() => onSelectPrompt(s.prompt)}
          >
            <s.icon size={20} />
            <strong>{s.title}</strong>
            <span>{s.detail}</span>
            <span className="suggestion-arrow">↗</span>
          </button>
        ))}
      </div>
      <div className="privacy-note">
        <ShieldCheck size={15} /> Saved in your workspace. Ready when you are.
      </div>
    </section>
  );
}
