"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { formatCurrency } from "@/lib/utils/currency";
import { calculatePayoffPlan } from "@/lib/ai/payoff-plan";

interface Debt {
  id: string;
  name: string;
  current_balance: number;
  interest_rate: number;
  minimum_payment: number;
}

export function PayoffSimulator({ debts }: { debts: Debt[] }) {
  const [extraPayment, setExtraPayment] = useState([0]);

  const activeDebts = debts.filter((d) => Number(d.current_balance) > 0);
  const totalMinimum = activeDebts.reduce((s, d) => s + Number(d.minimum_payment), 0);
  const monthlyAvailable = totalMinimum + extraPayment[0];

  const plan = useMemo(
    () =>
      calculatePayoffPlan(
        activeDebts.map((d) => ({
          ...d,
          current_balance: Number(d.current_balance),
          interest_rate: Number(d.interest_rate),
          minimum_payment: Number(d.minimum_payment),
        })),
        monthlyAvailable,
        "avalanche"
      ),
    [activeDebts, monthlyAvailable]
  );

  if (activeDebts.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Simulador de Quitação</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-sm">Valor extra mensal</span>
            <span className="text-sm font-semibold text-sky-600">
              {formatCurrency(extraPayment[0])}
            </span>
          </div>
          <Slider
            value={extraPayment}
            onValueChange={setExtraPayment}
            max={5000}
            step={50}
          />
        </div>

        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-sm text-muted-foreground">Pagamento Mensal</p>
            <p className="text-lg font-bold">{formatCurrency(monthlyAvailable)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Data de Quitação</p>
            <p className="text-lg font-bold">
              {plan.estimated_debt_free_date
                ? new Date(plan.estimated_debt_free_date).toLocaleDateString("pt-BR", {
                    month: "short",
                    year: "numeric",
                  })
                : "-"}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Economia em Juros</p>
            <p className="text-lg font-bold text-green-600">
              {formatCurrency(plan.total_interest_saved)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
