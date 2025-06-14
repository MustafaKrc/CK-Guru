// frontend/types/api/repository.ts

/**
 * Represents a repository as returned by the backend API.
 * Mirrors the RepositoryRead Pydantic schema.
 */
export interface Repository {
  id: number;
  name: string;
  git_url: string;
  created_at: string;
  updated_at: string;
  bot_patterns_count: number;
  datasets_count: number;
  github_issues_count: number;
  // These are not in the current RepositoryRead schema from backend
  // They are GAPs to be addressed later if needed for the list view.
  commits_count?: number;
  models_count?: number;
}

/**
 * Payload for creating a new repository.
 * Mirrors the RepositoryCreate Pydantic schema.
 */
export interface RepositoryCreatePayload {
  git_url: string;
}

/**
 * Payload for updating an existing repository.
 * Mirrors the RepositoryUpdate Pydantic schema.
 */
export interface RepositoryUpdatePayload {
  name?: string;
  git_url?: string;
}

export interface PaginatedRepositoryRead {
  items: Repository[];
  total: number;
  skip?: number;
  limit?: number;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
  nameFilter?: string;
}
