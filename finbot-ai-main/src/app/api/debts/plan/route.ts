import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { calculatePayoffPlan } from "@/lib/ai/payoff-plan";

export async function GET(request: NextRequest) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const method = (searchParams.get("method") || "avalanche") as "avalanche" | "snowball";
  const extraMonthly = Number(searchParams.get("extra") || 0);

  const { data: debts } = await supabase
    .from("debts")
    .select("id, name, current_balance, interest_rate, minimum_payment")
    .eq("user_id", user.id)
    .eq("status", "active");

  if (!debts?.length) {
    return NextResponse.json({ data: null, message: "Nenhuma dívida ativa" });
  }

  const totalMinimum = debts.reduce((s, d) => s + Number(d.minimum_payment), 0);
  const monthlyAvailable = totalMinimum + extraMonthly;

  const plan = calculatePayoffPlan(
    debts.map((d) => ({
      id: d.id,
      name: d.name,
      current_balance: Number(d.current_balance),
      interest_rate: Number(d.interest_rate),
      minimum_payment: Number(d.minimum_payment),
    })),
    monthlyAvailable,
    method
  );

  return NextResponse.json({ data: plan });
}
