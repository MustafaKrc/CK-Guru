// frontend/types/api/bot-pattern.ts
import { PatternTypeEnum } from "./enums"; // Use centralized enum

export interface BotPatternRead {
  id: number;
  pattern: string;
  pattern_type: PatternTypeEnum; // Use imported enum
  is_exclusion: boolean;
  description?: string | null;
  repository_id?: number | null;
}

export interface BotPatternCreatePayload {
  pattern: string;
  pattern_type: PatternTypeEnum;
  is_exclusion: boolean;
  description?: string | null;
  repository_id?: number | null;
}

export interface BotPatternUpdatePayload {
  pattern?: string;
  pattern_type?: PatternTypeEnum;
  is_exclusion?: boolean;
  description?: string | null;
}

// For paginated responses from backend
export interface PaginatedBotPatternRead {
  items: BotPatternRead[];
  total: number;
}