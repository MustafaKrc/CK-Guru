// frontend/types/api/commit.ts
import { CommitIngestionStatusEnum, FileChangeTypeEnum } from "./enums";
import { InferenceJobRead } from "./inference-job";

export interface CommitFileDiffRead {
  id: number;
  file_path: string;
  change_type: FileChangeTypeEnum;
  old_path?: string | null;
  diff_text: string;
}

export interface CommitDetailsRead {
  id: number;
  commit_hash: string;
  author_name: string;
  author_email: string;
  author_date: string; // ISO String
  message: string;
  parents: string[];
  stats_insertions: number;
  stats_deletions: number;
  stats_files_changed: number;
  file_diffs: CommitFileDiffRead[];
}

export interface CommitPageResponse {
  ingestion_status: CommitIngestionStatusEnum;
  details?: CommitDetailsRead | null;
  inference_jobs?: InferenceJobRead[] | null;
  celery_ingestion_task_id?: string | null;
}

export interface CommitListItem {
  commit_hash: string;
  author_name: string;
  author_date: string; // ISO String
  message_short: string;
  ingestion_status: CommitIngestionStatusEnum;
}

export interface PaginatedCommitList {
  items: CommitListItem[];
  total: number;
  skip?: number;
  limit?: number;
}