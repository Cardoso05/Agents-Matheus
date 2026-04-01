"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Wallet, CreditCard } from "lucide-react";
import { formatCurrency } from "@/lib/utils/currency";

interface KpiData {
  income: number;
  expenses: number;
  balance: number;
  totalDebt: number;
  incomeChange: number;
  expensesChange: number;
}

export function KpiCards({ userId }: { userId: string }) {
  const [data, setData] = useState<KpiData | null>(null);
  const supabase = createClient();

  useEffect(() => {
    async function fetchData() {
      const now = new Date();
      const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
      const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split("T")[0];
      const startOfPrevMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString().split("T")[0];
      const endOfPrevMonth = new Date(now.getFullYear(), now.getMonth(), 0).toISOString().split("T")[0];

      const [currentTx, prevTx, debts] = await Promise.all([
        supabase
          .from("transactions")
          .select("amount, type")
          .eq("user_id", userId)
          .gte("date", startOfMonth)
          .lte("date", endOfMonth),
        supabase
          .from("transactions")
          .select("amount, type")
          .eq("user_id", userId)
          .gte("date", startOfPrevMonth)
          .lte("date", endOfPrevMonth),
        supabase
          .from("debts")
          .select("current_balance")
          .eq("user_id", userId)
          .eq("status", "active"),
      ]);

      const income = (currentTx.data || [])
        .filter((t) => t.type === "income")
        .reduce((sum, t) => sum + Number(t.amount), 0);
      const expenses = Math.abs(
        (currentTx.data || [])
          .filter((t) => t.type === "expense")
          .reduce((sum, t) => sum + Number(t.amount), 0)
      );
      const prevIncome = (prevTx.data || [])
        .filter((t) => t.type === "income")
        .reduce((sum, t) => sum + Number(t.amount), 0);
      const prevExpenses = Math.abs(
        (prevTx.data || [])
          .filter((t) => t.type === "expense")
          .reduce((sum, t) => sum + Number(t.amount), 0)
      );
      const totalDebt = (debts.data || []).reduce(
        (sum, d) => sum + Number(d.current_balance),
        0
      );

      setData({
        income,
        expenses,
        balance: income - expenses,
        totalDebt,
        incomeChange: prevIncome > 0 ? ((income - prevIncome) / prevIncome) * 100 : 0,
        expensesChange: prevExpenses > 0 ? ((expenses - prevExpenses) / prevExpenses) * 100 : 0,
      });
    }
    fetchData();
  }, [userId, supabase]);

  if (!data) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="h-16 animate-pulse bg-slate-100 rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    {
      label: "Renda do Mês",
      value: data.income,
      change: data.incomeChange,
      icon: TrendingUp,
      color: "text-green-600",
      bg: "bg-green-50",
    },
    {
      label: "Gastos do Mês",
      value: data.expenses,
      change: data.expensesChange,
      icon: TrendingDown,
      color: "text-red-600",
      bg: "bg-red-50",
    },
    {
      label: "Saldo",
      value: data.balance,
      change: null,
      icon: Wallet,
      color: data.balance >= 0 ? "text-green-600" : "text-red-600",
      bg: data.balance >= 0 ? "bg-green-50" : "bg-red-50",
    },
    {
      label: "Dívida Total",
      value: data.totalDebt,
      change: null,
      icon: CreditCard,
      color: "text-orange-600",
      bg: "bg-orange-50",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{card.label}</span>
              <div className={`p-2 rounded-lg ${card.bg}`}>
                <card.icon className={`h-4 w-4 ${card.color}`} />
              </div>
            </div>
            <p className={`text-2xl font-bold mt-2 ${card.color}`}>
              {formatCurrency(card.value)}
            </p>
            {card.change !== null && (
              <p className="text-xs text-muted-foreground mt-1">
                {card.change >= 0 ? "+" : ""}
                {card.change.toFixed(1)}% vs mês anterior
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
