export interface ApiResponse<T = unknown> {
  data?: T;
  error?: string;
  message?: string;
}

export interface UploadResponse {
  transactions: import("./transaction").RawTransaction[];
  duplicates_count: number;
  new_count: number;
  file_id: string;
}

export interface CategorizeResponse {
  categorized: number;
  failed: number;
  results: {
    external_id: string;
    category_name: string;
    confidence: number;
  }[];
}
