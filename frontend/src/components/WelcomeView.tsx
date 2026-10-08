import React from "react";
import { BookOpen, Code2, PenLine, Image as ImageIcon } from "lucide-react";

interface WelcomeViewProps {
  onSelectPrompt: (prompt: string, autoWebSearch?: boolean) => void;
  imageSupported?: boolean;
  onTriggerImageMode?: () => void;
}

export function WelcomeView({
  onSelectPrompt,
  imageSupported = true,
  onTriggerImageMode,
}: WelcomeViewProps) {
  return (
    <section className="welcome" aria-label="Welcome screen">
      <div className="welcome-inner">
        <h1 className="welcome-heading">What can we <span className="welcome-gradient-text">work on?</span></h1>
        <p className="welcome-subtitle">Ask, explore, build, and create with Forma.</p>

        <div className="welcome-suggestions-grid">
          <button
            type="button"
            className="suggestion-tile"
            onClick={() =>
              onSelectPrompt(
                "Help me draft and polish a clear, concise piece of writing. Ask what topic to begin with.",
              )
            }
            aria-label="Write: Polish, draft, edit"
          >
            <div className="suggestion-tile-icon">
              <PenLine size={18} />
            </div>
            <div className="suggestion-tile-content">
              <span className="suggestion-tile-title">Write</span>
              <span className="suggestion-tile-desc">Polish, draft, edit</span>
            </div>
          </button>

          <button
            type="button"
            className="suggestion-tile"
            onClick={() =>
              onSelectPrompt(
                "Explain a complex concept to me in simple, intuitive terms. What would you like to explore?",
              )
            }
            aria-label="Learn: Explain anything"
          >
            <div className="suggestion-tile-icon">
              <BookOpen size={18} />
            </div>
            <div className="suggestion-tile-content">
              <span className="suggestion-tile-title">Learn</span>
              <span className="suggestion-tile-desc">Explain anything</span>
            </div>
          </button>

          <button
            type="button"
            className="suggestion-tile"
            onClick={() =>
              onSelectPrompt(
                "Write & debug code: Help me write a clean, robust function. Ask what it should do.",
              )
            }
            aria-label="Code (Write some code): Build, debug, solve"
          >
            <div className="suggestion-tile-icon">
              <Code2 size={18} />
            </div>
            <div className="suggestion-tile-content">
              <span className="suggestion-tile-title">Code</span>
              <span className="suggestion-tile-desc">Build, debug, solve</span>
            </div>
          </button>

          <button
            type="button"
            className="suggestion-tile"
            onClick={() => {
              if (onTriggerImageMode) {
                onTriggerImageMode();
              } else {
                onSelectPrompt("Create an image of: ");
              }
            }}
            aria-label="Create image: Visualize your ideas"
            disabled={!imageSupported}
            title={
              imageSupported
                ? "Switch to text-to-image mode"
                : "Image creation requires a supported image model"
            }
          >
            <div className="suggestion-tile-icon">
              <ImageIcon size={18} />
            </div>
            <div className="suggestion-tile-content">
              <span className="suggestion-tile-title">Create image</span>
              <span className="suggestion-tile-desc">Visualize your ideas</span>
            </div>
          </button>
        </div>
      </div>
    </section>
  );
}
