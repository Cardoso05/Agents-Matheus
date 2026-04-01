"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils/currency";
import { AlertTriangle, Scissors, Phone, CreditCard, ShoppingBag, Check, ArrowRight } from "lucide-react";
import { toast } from "sonner";

interface CutSuggestion {
  category: string;
  currentSpend: number;
  suggestedCut: number;
  description: string;
  icon: "scissors" | "phone" | "credit-card" | "shopping-bag";
  accepted: boolean;
}

interface DebtDue {
  name: string;
  amount: number;
  dueDay: number;
  canPayMinimum: boolean;
}

export default function EmergencyPage() {
  const [income, setIncome] = useState(0);
  const [expenses, setExpenses] = useState(0);
  const [debtPayments, setDebtPayments] = useState(0);
  const [cuts, setCuts] = useState<CutSuggestion[]>([]);
  const [debtsDue, setDebtsDue] = useState<DebtDue[]>([]);
  const [loading, setLoading] = useState(true);
  const supabase = createClient();

  useEffect(() => {
    async function fetchData() {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split("T")[0];
      const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
      const daysPassed = now.getDate();
      const daysRemaining = daysInMonth - daysPassed;

      // Fetch profile for income
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data: profile } = await supabase
        .from("profiles")
        .select("monthly_income, variable_income")
        .eq("id", user.id)
        .single();

      const monthlyIncome = Number(profile?.monthly_income || 0) + Number(profile?.variable_income || 0);

      // Fetch transactions this month
      const { data: txs } = await supabase
        .from("transactions")
        .select("amount, type, category:categories(name, group_name)")
        .gte("date", start)
        .lte("date", end);

      const incomeTotal = (txs || [])
        .filter((t) => t.type === "income")
        .reduce((s, t) => s + Number(t.amount), 0);

      const expenseTotal = Math.abs(
        (txs || [])
          .filter((t) => t.type === "expense")
          .reduce((s, t) => s + Number(t.amount), 0)
      );

      // Group by category
      const catSpending = new Map<string, { total: number; group: string }>();
      for (const tx of txs || []) {
        if (tx.type === "expense") {
          const cat = (tx.category as unknown as { name: string; group_name: string });
          const name = cat?.name || "Outros";
          const group = cat?.group_name || "outros";
          const current = catSpending.get(name) || { total: 0, group };
          catSpending.set(name, { total: current.total + Math.abs(Number(tx.amount)), group });
        }
      }

      // Identify cuttable categories
      const cuttableGroups = ["lazer", "pessoal", "alimentação"];
      const cuttableCategories = ["Delivery", "Streaming", "Entretenimento", "Uber/99", "Roupas", "Estética", "Restaurante"];

      const suggestions: CutSuggestion[] = [];
      for (const [catName, data] of Array.from(catSpending.entries())) {
        if (cuttableCategories.includes(catName) || cuttableGroups.includes(data.group)) {
          if (data.total > 50) {
            const projectedRemaining = (data.total / daysPassed) * daysRemaining;
            suggestions.push({
              category: catName,
              currentSpend: data.total,
              suggestedCut: Math.round(projectedRemaining * 0.7),
              description: `Cortar ${catName} pelo resto do mês: economia de ~${formatCurrency(Math.round(projectedRemaining * 0.7))}`,
              icon: catName.includes("Delivery") || catName.includes("Restaurante") ? "shopping-bag" : "scissors",
              accepted: false,
            });
          }
        }
      }
      suggestions.sort((a, b) => b.suggestedCut - a.suggestedCut);

      // Debts due this month
      const { data: debts } = await supabase
        .from("debts")
        .select("name, minimum_payment, due_day, current_balance")
        .eq("user_id", user.id)
        .eq("status", "active");

      const debtPaymentTotal = (debts || []).reduce((s, d) => s + Number(d.minimum_payment), 0);

      const upcomingDebts: DebtDue[] = (debts || [])
        .filter((d) => d.due_day && d.due_day >= now.getDate())
        .map((d) => ({
          name: d.name,
          amount: Number(d.minimum_payment),
          dueDay: d.due_day!,
          canPayMinimum: true,
        }));

      const effectiveIncome = incomeTotal > 0 ? incomeTotal : monthlyIncome;
      setIncome(effectiveIncome);
      setExpenses(expenseTotal);
      setDebtPayments(debtPaymentTotal);
      setCuts(suggestions);
      setDebtsDue(upcomingDebts);
      setLoading(false);
    }
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggleCut(index: number) {
    setCuts((prev) =>
      prev.map((c, i) => (i === index ? { ...c, accepted: !c.accepted } : c))
    );
  }

  const totalSavings = cuts.filter((c) => c.accepted).reduce((s, c) => s + c.suggestedCut, 0);
  const remaining = income - expenses - debtPayments;
  const projectedWithCuts = remaining + totalSavings;

  const iconMap = {
    scissors: Scissors,
    phone: Phone,
    "credit-card": CreditCard,
    "shopping-bag": ShoppingBag,
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-slate-100 animate-pulse rounded" />
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 bg-slate-100 animate-pulse rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
          <AlertTriangle className="h-5 w-5 text-red-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Modo Emergência</h1>
          <p className="text-muted-foreground">O dinheiro está curto? Vamos resolver juntos.</p>
        </div>
      </div>

      {/* Diagnóstico */}
      <Card className={remaining < 0 ? "border-red-300 bg-red-50" : "border-yellow-300 bg-yellow-50"}>
        <CardContent className="p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-xs text-muted-foreground">Renda do mês</p>
              <p className="text-xl font-bold text-green-600">{formatCurrency(income)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Gastos até agora</p>
              <p className="text-xl font-bold text-red-600">{formatCurrency(expenses)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Parcelas pendentes</p>
              <p className="text-xl font-bold text-orange-600">{formatCurrency(debtPayments)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{remaining >= 0 ? "Sobra" : "Falta"}</p>
              <p className={`text-xl font-bold ${remaining >= 0 ? "text-green-600" : "text-red-600"}`}>
                {formatCurrency(Math.abs(remaining))}
              </p>
            </div>
          </div>
          {remaining < 0 && (
            <p className="text-center text-sm text-red-700 mt-4 font-medium">
              Você precisa de {formatCurrency(Math.abs(remaining))} para fechar o mês. Veja as sugestões abaixo.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Sugestões de corte */}
      {cuts.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Onde cortar agora</h2>
          <p className="text-sm text-muted-foreground">Selecione os cortes que vai fazer. O saldo atualiza em tempo real.</p>

          {cuts.map((cut, i) => {
            const Icon = iconMap[cut.icon];
            return (
              <Card
                key={i}
                className={`cursor-pointer transition-all ${
                  cut.accepted ? "border-green-400 bg-green-50" : "hover:border-slate-300"
                }`}
                onClick={() => toggleCut(i)}
              >
                <CardContent className="p-4 flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    cut.accepted ? "bg-green-100" : "bg-slate-100"
                  }`}>
                    {cut.accepted ? (
                      <Check className="h-5 w-5 text-green-600" />
                    ) : (
                      <Icon className="h-5 w-5 text-slate-500" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-sm">{cut.description}</p>
                    <p className="text-xs text-muted-foreground">
                      Gasto atual: {formatCurrency(cut.currentSpend)}
                    </p>
                  </div>
                  <p className={`font-bold text-sm ${cut.accepted ? "text-green-600" : "text-slate-600"}`}>
                    +{formatCurrency(cut.suggestedCut)}
                  </p>
                </CardContent>
              </Card>
            );
          })}

          {/* Resultado com cortes */}
          <Card className="border-sky-300 bg-sky-50">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Com os cortes selecionados</p>
                  <p className="text-xs text-muted-foreground">
                    Economia total: {formatCurrency(totalSavings)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">Projeção de sobra</p>
                  <p className={`text-xl font-bold ${projectedWithCuts >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {formatCurrency(projectedWithCuts)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Parcelas do mês */}
      {debtsDue.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Parcelas pendentes este mês</h2>
          {debtsDue.map((debt, i) => (
            <Card key={i}>
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CreditCard className="h-5 w-5 text-orange-500" />
                  <div>
                    <p className="font-medium text-sm">{debt.name}</p>
                    <p className="text-xs text-muted-foreground">Vence dia {debt.dueDay}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-sm">{formatCurrency(debt.amount)}</p>
                  {remaining < 0 && (
                    <p className="text-xs text-orange-600">Considere pagar só o mínimo</p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Dicas de renda extra */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Precisa de renda extra rápida?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            { text: "Venda itens que não usa (OLX, Enjoei, Facebook Marketplace)", action: "Pode render R$ 200-2.000" },
            { text: "Faça bicos esta semana (99, Uber, entregas)", action: "Pode render R$ 500-1.500/mês" },
            { text: "Ofereça serviços (limpeza, consertos, aulas)", action: "Pode render R$ 100-500/semana" },
            { text: "Ligue para o banco e renegocie juros/prazos", action: "Pode reduzir parcela em 30-50%" },
          ].map((tip, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50">
              <ArrowRight className="h-4 w-4 text-sky-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium">{tip.text}</p>
                <p className="text-xs text-muted-foreground">{tip.action}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* CTA para chat */}
      <Card className="border-sky-300">
        <CardContent className="p-6 text-center space-y-3">
          <p className="font-medium">Precisa de ajuda personalizada?</p>
          <p className="text-sm text-muted-foreground">
            O FinBot pode te ajudar a montar um plano específico para este mês.
          </p>
          <Button
            onClick={() => {
              toast.info("Abra o chat no canto inferior direito e descreva sua situação!");
            }}
          >
            Falar com FinBot
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
