export type DebtStatus = "active" | "negotiating" | "paid_off";
export type PayoffMethod = "avalanche" | "snowball";

export interface Debt {
  id: string;
  user_id: string;
  name: string;
  creditor: string | null;
  original_amount: number;
  current_balance: number;
  interest_rate: number;
  minimum_payment: number;
  installment_amount: number | null;
  remaining_installments: number | null;
  due_day: number | null;
  priority: number;
  status: DebtStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DebtPayment {
  id: string;
  debt_id: string;
  date: string;
  amount: number;
  is_extra: boolean;
  notes: string | null;
  created_at: string;
}

export interface PayoffPlan {
  method: PayoffMethod;
  monthly_available: number;
  debts: PayoffDebtPlan[];
  total_interest_saved: number;
  estimated_debt_free_date: string;
}

export interface PayoffDebtPlan {
  debt_id: string;
  name: string;
  monthly_payment: number;
  payoff_date: string;
  total_paid: number;
  total_interest: number;
  schedule: { month: string; payment: number; balance: number }[];
}
