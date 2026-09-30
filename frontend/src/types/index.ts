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
  default_model: string;
  key_url?: string;
  has_key?: boolean;
}

export interface ModelsResponse {
  provider: string;
  providers: ProviderInfo[];
  models: string[];
  model_details: ModelDetail[];
  default: string;
}
