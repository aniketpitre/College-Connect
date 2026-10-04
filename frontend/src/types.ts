export type Language = "en" | "hi" | "mr";

export type Category =
  | "admissions"
  | "fees"
  | "examinations"
  | "placements"
  | "hostel"
  | "notices";

export interface SourceRef {
  title: string;
  document: string;
  section: string;
}

export interface QueryResponse {
  answer: string;
  language: Language;
  category: Category;
  sources: SourceRef[];
  confidence: number;
  grounded: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: SourceRef[];
  grounded?: boolean;
  confidence?: number;
  isError?: boolean;
}

export interface LoggedQuery {
  created_at: string;
  question: string;
  language: Language;
  category: Category | null;
  category_filter: Category | null;
  grounded: boolean;
  confidence: number;
  sources: string[];
  latency_ms: number;
}

export interface AdminStats {
  analytics_enabled: boolean;
  pipeline: {
    retrieval: "vector" | "bm25";
    embedding_model: string | null;
    generation: string;
    chunks: number;
    documents: number;
  };
  days?: number;
  total_queries?: number;
  all_time_queries?: number;
  grounded_rate?: number | null;
  avg_latency_ms?: number | null;
  avg_confidence?: number | null;
  by_category?: Partial<Record<Category, number>>;
  by_language?: Partial<Record<Language, number>>;
  knowledge_gaps?: LoggedQuery[];
  recent?: LoggedQuery[];
}
