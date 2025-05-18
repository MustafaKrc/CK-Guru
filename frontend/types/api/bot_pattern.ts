// frontend/types/api/bot_pattern.ts

// Mirrors shared/db/models/bot_pattern.py -> PatternTypeEnum
// Or use a string type if you prefer not to duplicate enums strictly on frontend for now
export enum PatternTypeEnumFE { // FE suffix to avoid name clash if you also have backend enums in types
  REGEX = "REGEX",
  WILDCARD = "WILDCARD",
  EXACT = "EXACT",
}

// Mirrors shared/schemas/bot_pattern.py -> BotPatternRead
export interface BotPatternRead {
  id: number;
  pattern: string;
  pattern_type: PatternTypeEnumFE | string; // Allow string for flexibility from backend
  is_exclusion: boolean;
  description?: string | null;
  repository_id?: number | null; // Null for global patterns
}

// Mirrors shared/schemas/bot_pattern.py -> BotPatternCreate
export interface BotPatternCreatePayload {
  pattern: string;
  pattern_type: PatternTypeEnumFE | string;
  is_exclusion: boolean;
  description?: string | null;
  repository_id?: number | null;
}

// Mirrors shared/schemas/bot_pattern.py -> BotPatternUpdate
export interface BotPatternUpdatePayload {
  pattern?: string;
  pattern_type?: PatternTypeEnumFE | string;
  is_exclusion?: boolean;
  description?: string | null;
  // repository_id is typically not updated via this payload
}