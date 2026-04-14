import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { RevenueExpensesChart } from "@/components/dashboard/revenue-expenses-chart";
import { CategoryPieChart } from "@/components/dashboard/category-pie-chart";
import { RecentTransactions } from "@/components/dashboard/recent-transactions";

export default async function DashboardPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) return null;

  const { data: profile } = await supabase
    .from("profiles")
    .select("onboarding_completed")
    .eq("id", user.id)
    .single();

  if (!profile?.onboarding_completed) {
    redirect("/onboarding");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Visão geral das suas finanças</p>
      </div>

      <KpiCards userId={user.id} />

      <div className="grid lg:grid-cols-2 gap-6">
        <RevenueExpensesChart userId={user.id} />
        <CategoryPieChart userId={user.id} />
      </div>

      <RecentTransactions userId={user.id} />
    </div>
  );
}
