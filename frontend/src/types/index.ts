import { LucideIcon } from "lucide-react";
import { Attachment, Conversation, Message, WebSearchResult, AgentStep } from "../services/api";

export type { Attachment, Conversation, Message, WebSearchResult, AgentStep };

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
  supports_vision?: boolean;
  chat_compatible?: boolean;
  supports_image_generation?: boolean;
  supports_reasoning?: boolean;
  supports_search?: boolean;
  is_fast?: boolean;
  capabilities?: string[];
  provider?: string;
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
  models?: ModelDetail[];
}

export type FeatureCoverage = Record<string, {
  label: string;
  status: string;
  message: string;
  options: {provider: string; model: string; reason: string}[];
}>;

export interface ModelsResponse {
  feature_coverage?: FeatureCoverage;
  provider: string;
  providers: ProviderInfo[];
  models: string[];
  model_details: ModelDetail[];
  default: string;
  auto?: {
    id: string;
    name: string;
    badge: string;
    description: string;
  };
}
