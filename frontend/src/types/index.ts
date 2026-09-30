import { LucideIcon } from "lucide-react";
import { Attachment, Conversation, Message, WebSearchResult } from "../services/api";

export type { Attachment, Conversation, Message, WebSearchResult };

export interface Suggestion {
  icon: LucideIcon;
  title: string;
  detail: string;
  prompt: string;
}

export interface QuestionPrompt {
  title: string;
  value?: string;
  resolve: (value: string | null) => void;
}

export interface ModelDetail {
  id: string;
  name: string;
  badge?: string;
  description?: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  tagline?: string;
  configured?: boolean;
  working?: boolean;
  status?: string;
  error?: string | null;
  default_model: string;
  key_url?: string;
}

export interface ModelsResponse {
  provider: string;
  providers: ProviderInfo[];
  models: string[];
  model_details: ModelDetail[];
  default: string;
}
