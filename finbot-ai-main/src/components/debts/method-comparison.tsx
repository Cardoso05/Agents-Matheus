"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/utils/currency";
import { calculatePayoffPlan } from "@/lib/ai/payoff-plan";

interface Debt {
  id: string;
  name: string;
  current_balance: number;
  interest_rate: number;
  minimum_payment: number;
}

export function MethodComparison({ debts }: { debts: Debt[] }) {
  const activeDebts = debts.filter((d) => Number(d.current_balance) > 0);
  const totalMinimum = activeDebts.reduce((s, d) => s + Number(d.minimum_payment), 0);
  const monthlyAvailable = totalMinimum * 1.2; // 20% extra

  const mapped = activeDebts.map((d) => ({
    ...d,
    current_balance: Number(d.current_balance),
    interest_rate: Number(d.interest_rate),
    minimum_payment: Number(d.minimum_payment),
  }));

  const avalanche = useMemo(
    () => calculatePayoffPlan(mapped, monthlyAvailable, "avalanche"),
    [mapped, monthlyAvailable]
  );
  const snowball = useMemo(
    () => calculatePayoffPlan(mapped, monthlyAvailable, "snowball"),
    [mapped, monthlyAvailable]
  );

  if (activeDebts.length === 0) return null;

  const avalancheWins =
    avalanche.total_interest_saved >= snowball.total_interest_saved;

  const methods = [
    { label: "Avalanche", desc: "Maior juros primeiro", plan: avalanche, best: avalancheWins },
    { label: "Bola de Neve", desc: "Menor saldo primeiro", plan: snowball, best: !avalancheWins },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Comparação de Métodos</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid md:grid-cols-2 gap-4">
          {methods.map((m) => (
            <div
              key={m.label}
              className={`p-4 rounded-lg border-2 ${
                m.best ? "border-sky-500 bg-sky-50" : "border-slate-200"
              }`}
            >
              <div className="flex items-center gap-2 mb-3">
                <h3 className="font-semibold">{m.label}</h3>
                {m.best && <Badge>Recomendado</Badge>}
              </div>
              <p className="text-xs text-muted-foreground mb-3">{m.desc}</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Data de quitação</span>
                  <span className="font-medium">
                    {m.plan.estimated_debt_free_date
                      ? new Date(m.plan.estimated_debt_free_date).toLocaleDateString("pt-BR", {
                          month: "short",
                          year: "numeric",
                        })
                      : "-"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Economia em juros</span>
                  <span className="font-medium text-green-600">
                    {formatCurrency(m.plan.total_interest_saved)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Ordem de pagamento</span>
                  <span className="font-medium text-xs">
                    {m.plan.debts.map((d) => d.name).join(" → ")}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
