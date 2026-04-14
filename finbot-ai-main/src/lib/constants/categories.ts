export const CATEGORY_GROUPS = {
  moradia: { label: "Moradia", color: "#6366F1", type: "necessity" as const },
  transporte: { label: "Transporte", color: "#F59E0B", type: "necessity" as const },
  alimentação: { label: "Alimentação", color: "#10B981", type: "necessity" as const },
  saúde: { label: "Saúde", color: "#EF4444", type: "necessity" as const },
  educação: { label: "Educação", color: "#8B5CF6", type: "want" as const },
  lazer: { label: "Lazer", color: "#EC4899", type: "want" as const },
  trabalho: { label: "Trabalho", color: "#0EA5E9", type: "necessity" as const },
  financeiro: { label: "Financeiro", color: "#DC2626", type: "saving" as const },
  pessoal: { label: "Pessoal", color: "#D946EF", type: "want" as const },
  renda: { label: "Renda", color: "#16A34A", type: "income" as const },
  outros: { label: "Outros", color: "#6B7280", type: "want" as const },
} as const;

export type CategoryGroupKey = keyof typeof CATEGORY_GROUPS;
export type BudgetType = "necessity" | "want" | "saving" | "income";
