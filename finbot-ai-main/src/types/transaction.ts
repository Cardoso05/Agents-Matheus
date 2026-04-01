export type TransactionType = "income" | "expense" | "transfer";
export type TransactionSource = "upload_csv" | "upload_ofx" | "upload_pdf" | "upload_photo" | "open_finance" | "manual";

export interface RawTransaction {
  date: string;
  amount: number;
  description: string;
  type: TransactionType;
  bank_slug: string;
  external_id: string;
}

export interface CategorizedTransaction extends RawTransaction {
  category_id: string;
  category_name: string;
  clean_description: string;
  confidence: number;
  is_recurring: boolean;
}

export interface Transaction {
  id: string;
  user_id: string;
  account_id: string | null;
  category_id: string | null;
  date: string;
  amount: number;
  description: string;
  clean_description: string | null;
  type: TransactionType;
  source: TransactionSource;
  confidence: number;
  is_confirmed: boolean;
  is_recurring: boolean;
  external_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  category?: Category;
}

export interface Category {
  id: string;
  user_id: string | null;
  name: string;
  group_name: string;
  icon: string;
  color: string;
  is_system: boolean;
}
