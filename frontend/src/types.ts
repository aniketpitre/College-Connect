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
