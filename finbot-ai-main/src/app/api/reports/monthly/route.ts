import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { generateMonthlyReport } from "@/lib/ai/monthly-report";

export async function POST() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
    const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split("T")[0];
    const prevStart = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString().split("T")[0];
    const prevEnd = new Date(now.getFullYear(), now.getMonth(), 0).toISOString().split("T")[0];

    const [currentTxs, prevTxs, debts] = await Promise.all([
      supabase
        .from("transactions")
        .select("amount, type, category:categories(name, group_name)")
        .eq("user_id", user.id)
        .gte("date", monthStart)
        .lte("date", monthEnd),
      supabase
        .from("transactions")
        .select("amount, type")
        .eq("user_id", user.id)
        .gte("date", prevStart)
        .lte("date", prevEnd),
      supabase
        .from("debts")
        .select("current_balance, original_amount")
        .eq("user_id", user.id)
        .eq("status", "active"),
    ]);

    const income = (currentTxs.data || [])
      .filter((t) => t.type === "income")
      .reduce((s, t) => s + Number(t.amount), 0);
    const expenses = Math.abs(
      (currentTxs.data || [])
        .filter((t) => t.type === "expense")
        .reduce((s, t) => s + Number(t.amount), 0)
    );

    const prevIncome = (prevTxs.data || [])
      .filter((t) => t.type === "income")
      .reduce((s, t) => s + Number(t.amount), 0);
    const prevExpenses = Math.abs(
      (prevTxs.data || [])
        .filter((t) => t.type === "expense")
        .reduce((s, t) => s + Number(t.amount), 0)
    );

    // Category breakdown
    const catMap = new Map<string, number>();
    for (const tx of currentTxs.data || []) {
      if (tx.type === "expense") {
        const cat = (tx.category as unknown as { name: string })?.name || "Outros";
        catMap.set(cat, (catMap.get(cat) || 0) + Math.abs(Number(tx.amount)));
      }
    }

    const debtTotal = (debts.data || []).reduce((s, d) => s + Number(d.current_balance), 0);
    const debtPaid = (debts.data || []).reduce(
      (s, d) => s + (Number(d.original_amount) - Number(d.current_balance)),
      0
    );

    const reportResult = await generateMonthlyReport({
      month: monthStart,
      totalIncome: income,
      totalExpenses: expenses,
      categoryBreakdown: Array.from(catMap.entries()).map(([name, total]) => ({ name, total })),
      previousMonth: { income: prevIncome, expenses: prevExpenses },
      debtProgress: debts.data?.length ? { total: debtTotal, paid: debtPaid } : null,
    });

    // Save report
    const { data: report, error } = await supabase
      .from("reports")
      .upsert(
        {
          user_id: user.id,
          month: monthStart,
          health_score: reportResult.health_score,
          total_income: income,
          total_expenses: expenses,
          total_balance: income - expenses,
          summary: reportResult.summary,
          recommendations: reportResult.recommendations,
        },
        { onConflict: "user_id,month" }
      )
      .select()
      .single();

    if (error) throw error;

    return NextResponse.json(report);
  } catch (error) {
    console.error("Report error:", error);
    return NextResponse.json({ error: "Erro ao gerar relatório" }, { status: 500 });
  }
}
