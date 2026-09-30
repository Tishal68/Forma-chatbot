import React, { useEffect, useRef, useState } from "react";
import { QuestionPrompt } from "../types";

interface ConfirmDialogProps {
  question: QuestionPrompt | null;
  onSettle: (value: string | null) => void;
}

export function ConfirmDialog({ question, onSettle }: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    if (question) {
      setAnswer(question.value || "");
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [question]);

  return (
    <dialog ref={dialogRef} onCancel={() => onSettle(null)}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSettle(question?.value !== undefined ? answer : "confirmed");
        }}
      >
        <h2 className="question-title">{question?.title}</h2>
        {question?.value !== undefined && (
          <input
            className="rename-input"
            aria-label="Conversation title"
            autoFocus
            maxLength={80}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
          />
        )}
        <div className="confirm-actions">
          <button type="button" onClick={() => onSettle(null)}>
            Cancel
          </button>
          <button type="submit" className="confirm-primary">
            {question?.value !== undefined ? "Save" : "Confirm"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
