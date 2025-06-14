// frontend/types/api/bot-pattern.ts

export interface BotPatternRead {
  id: number;
  pattern: string;
  is_exclusion: boolean;
  description?: string | null;
  repository_id?: number | null;
}

export interface BotPatternCreatePayload {
  pattern: string;
  is_exclusion: boolean;
  description?: string | null;
  repository_id?: number | null;
}

export interface BotPatternUpdatePayload {
  pattern?: string;
  is_exclusion?: boolean;
  description?: string | null;
}

export interface PaginatedBotPatternRead {
  items: BotPatternRead[];
  total: number;
}
