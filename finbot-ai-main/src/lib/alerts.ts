import { SupabaseClient } from "@supabase/supabase-js";
import { formatCurrency } from "@/lib/utils/currency";

type AlertType =
  | "overspend"
  | "risk"
  | "due_date"
  | "saving_opportunity"
  | "goal_reached"
  | "low_income";

interface AlertInsert {
  user_id: string;
  type: AlertType;
  title: string;
  message: string;
  metadata: Record<string, unknown>;
}

async function alertExistsToday(
  userId: string,
  supabase: SupabaseClient,
  type: AlertType,
  metadataKey: string,
  metadataValue: string
): Promise<boolean> {
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);

  const { data } = await supabase
    .from("alerts")
    .select("id")
    .eq("user_id", userId)
    .eq("type", type)
    .gte("created_at", todayStart.toISOString())
    .contains("metadata", { [metadataKey]: metadataValue })
    .limit(1);

  return (data?.length ?? 0) > 0;
}

async function insertAlert(supabase: SupabaseClient, alert: AlertInsert) {
  const { error } = await supabase.from("alerts").insert(alert);
  if (error) {
    console.error("Failed to insert alert:", error.message);
  }
}

// ─── Due Date Alerts ────────────────────────────────────────────────
async function checkDueDateAlerts(
  userId: string,
  supabase: SupabaseClient
): Promise<void> {
  const { data: debts } = await supabase
    .from("debts")
    .select("id, name, due_day, minimum_payment")
    .eq("user_id", userId)
    .eq("status", "active")
    .not("due_day", "is", null);

  if (!debts || debts.length === 0) return;

  const today = new Date();
  const currentDay = today.getDate();

  // Calculate what day is 3 days from now (handle month boundary)
  const threeDaysFromNow = new Date(today);
  threeDaysFromNow.setDate(today.getDate() + 3);
  const dayIn3Days = threeDaysFromNow.getDate();

  for (const debt of debts) {
    const dueDay = debt.due_day as number;
    const payment = formatCurrency(debt.minimum_payment);
    const debtName = debt.name;
    const metaKey = "debt_id";
    const metaValue = debt.id as string;

    if (dueDay === currentDay) {
      const exists = await alertExistsToday(
        userId,
        supabase,
        "due_date",
        metaKey,
        metaValue
      );
      if (!exists) {
        await insertAlert(supabase, {
          user_id: userId,
          type: "due_date",
          title: "Parcela vence HOJE!",
          message: `Hoje é dia de pagar ${payment} do ${debtName}!`,
          metadata: { debt_id: metaValue, due_day: dueDay, variant: "today" },
        });
      }
    } else if (dueDay === dayIn3Days) {
      const exists = await alertExistsToday(
        userId,
        supabase,
        "due_date",
        metaKey,
        metaValue
      );
      if (!exists) {
        await insertAlert(supabase, {
          user_id: userId,
          type: "due_date",
          title: "Parcela vence em 3 dias",
          message: `A parcela de ${payment} do ${debtName} vence dia ${dueDay}. Não esqueça!`,
          metadata: {
            debt_id: metaValue,
            due_day: dueDay,
            variant: "3_days",
          },
        });
      }
    }
  }
}

// ─── Overspend Alerts ───────────────────────────────────────────────
async function checkOverspendAlerts(
  userId: string,
  supabase: SupabaseClient
): Promise<void> {
  const now = new Date();
  const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    .toISOString()
    .split("T")[0];
  const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1)
    .toISOString()
    .split("T")[0];

  // Get expenses for the current month grouped by category
  const { data: currentExpenses } = await supabase
    .from("transactions")
    .select("amount, category_id, categories(name)")
    .eq("user_id", userId)
    .eq("type", "expense")
    .gte("date", currentMonthStart)
    .lt("date", nextMonthStart);

  if (!currentExpenses || currentExpenses.length === 0) return;

  // Group current month by category
  const currentByCategory: Record<
    string,
    { total: number; name: string }
  > = {};
  for (const tx of currentExpenses) {
    if (!tx.category_id) continue;
    const catName =
      (tx.categories as unknown as { name: string })?.name ?? "Outros";
    if (!currentByCategory[tx.category_id]) {
      currentByCategory[tx.category_id] = { total: 0, name: catName };
    }
    currentByCategory[tx.category_id].total += Math.abs(tx.amount);
  }

  // Get the 3-month average per category
  const threeMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 3, 1)
    .toISOString()
    .split("T")[0];

  const { data: pastExpenses } = await supabase
    .from("transactions")
    .select("amount, category_id")
    .eq("user_id", userId)
    .eq("type", "expense")
    .gte("date", threeMonthsAgo)
    .lt("date", currentMonthStart);

  if (!pastExpenses || pastExpenses.length === 0) return;

  const pastByCategory: Record<string, number> = {};
  for (const tx of pastExpenses) {
    if (!tx.category_id) continue;
    pastByCategory[tx.category_id] =
      (pastByCategory[tx.category_id] ?? 0) + Math.abs(tx.amount);
  }

  // Compare current vs average
  for (const [catId, current] of Object.entries(currentByCategory)) {
    const pastTotal = pastByCategory[catId];
    if (!pastTotal) continue;

    const avg = pastTotal / 3;
    if (avg === 0) continue;

    const pct = (current.total / avg) * 100;
    if (pct > 120) {
      const exists = await alertExistsToday(
        userId,
        supabase,
        "overspend",
        "category_id",
        catId
      );
      if (!exists) {
        await insertAlert(supabase, {
          user_id: userId,
          type: "overspend",
          title: `Gasto elevado em ${current.name}`,
          message: `Seus gastos com ${current.name} já chegaram a ${formatCurrency(current.total)}, ${Math.round(pct)}% acima da média de ${formatCurrency(avg)}.`,
          metadata: {
            category_id: catId,
            current_total: current.total,
            average: avg,
            percentage: Math.round(pct),
          },
        });
      }
    }
  }
}

// ─── Budget Risk Alerts ─────────────────────────────────────────────
async function checkBudgetRiskAlerts(
  userId: string,
  supabase: SupabaseClient
): Promise<void> {
  // Get user's monthly income from profile
  const { data: profile } = await supabase
    .from("profiles")
    .select("monthly_income")
    .eq("id", userId)
    .single();

  if (!profile?.monthly_income) return;

  const income = profile.monthly_income as number;

  const now = new Date();
  const dayOfMonth = now.getDate();
  const daysInMonth = new Date(
    now.getFullYear(),
    now.getMonth() + 1,
    0
  ).getDate();

  if (dayOfMonth < 5) return; // too early to project

  const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    .toISOString()
    .split("T")[0];
  const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1)
    .toISOString()
    .split("T")[0];

  const { data: expenses } = await supabase
    .from("transactions")
    .select("amount")
    .eq("user_id", userId)
    .eq("type", "expense")
    .gte("date", currentMonthStart)
    .lt("date", nextMonthStart);

  if (!expenses || expenses.length === 0) return;

  const totalSpent = expenses.reduce(
    (sum, tx) => sum + Math.abs(tx.amount),
    0
  );
  const dailyRate = totalSpent / dayOfMonth;
  const projected = dailyRate * daysInMonth;

  if (projected > income) {
    const exists = await alertExistsToday(
      userId,
      supabase,
      "risk",
      "variant",
      "budget_risk"
    );
    if (!exists) {
      await insertAlert(supabase, {
        user_id: userId,
        type: "risk",
        title: "Alerta de orçamento",
        message: `No ritmo atual, seus gastos devem chegar a ${formatCurrency(projected)}. Sua renda é ${formatCurrency(income)}. Considere reduzir gastos.`,
        metadata: {
          variant: "budget_risk",
          projected,
          income,
          daily_rate: dailyRate,
        },
      });
    }
  }
}

// ─── Income Received Alert ──────────────────────────────────────────
async function checkIncomeReceivedAlert(
  userId: string,
  supabase: SupabaseClient
): Promise<void> {
  const { data: profile } = await supabase
    .from("profiles")
    .select("monthly_income")
    .eq("id", userId)
    .single();

  if (!profile?.monthly_income) return;

  const income = profile.monthly_income as number;
  const threshold = income * 0.4;

  const todayStr = new Date().toISOString().split("T")[0];

  const { data: incomes } = await supabase
    .from("transactions")
    .select("id, amount")
    .eq("user_id", userId)
    .eq("type", "income")
    .eq("date", todayStr)
    .gte("amount", threshold);

  if (!incomes || incomes.length === 0) return;

  for (const tx of incomes) {
    const exists = await alertExistsToday(
      userId,
      supabase,
      "saving_opportunity",
      "transaction_id",
      tx.id as string
    );
    if (!exists) {
      const suggestedSaving = Math.round(tx.amount * 0.3);
      await insertAlert(supabase, {
        user_id: userId,
        type: "saving_opportunity",
        title: "Renda recebida!",
        message: `Depósito de ${formatCurrency(tx.amount)} detectado. Separe ${formatCurrency(suggestedSaving)} para dívidas antes de gastar!`,
        metadata: {
          transaction_id: tx.id,
          amount: tx.amount,
          suggested_saving: suggestedSaving,
        },
      });
    }
  }
}

// ─── Main Entry Point ───────────────────────────────────────────────
export async function checkAndCreateAlerts(
  userId: string,
  supabase: SupabaseClient
): Promise<void> {
  await Promise.all([
    checkDueDateAlerts(userId, supabase),
    checkOverspendAlerts(userId, supabase),
    checkBudgetRiskAlerts(userId, supabase),
    checkIncomeReceivedAlert(userId, supabase),
  ]);
}
