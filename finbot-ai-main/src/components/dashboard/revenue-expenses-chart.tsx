"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { formatCurrency } from "@/lib/utils/currency";

interface MonthData {
  month: string;
  income: number;
  expenses: number;
}

export function RevenueExpensesChart({ userId }: { userId: string }) {
  const [data, setData] = useState<MonthData[]>([]);
  const supabase = createClient();

  useEffect(() => {
    async function fetchData() {
      const months: MonthData[] = [];
      const now = new Date();

      for (let i = 5; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const start = d.toISOString().split("T")[0];
        const end = new Date(d.getFullYear(), d.getMonth() + 1, 0)
          .toISOString()
          .split("T")[0];

        const { data: txs } = await supabase
          .from("transactions")
          .select("amount, type")
          .eq("user_id", userId)
          .gte("date", start)
          .lte("date", end);

        const income = (txs || [])
          .filter((t) => t.type === "income")
          .reduce((s, t) => s + Number(t.amount), 0);
        const expenses = Math.abs(
          (txs || [])
            .filter((t) => t.type === "expense")
            .reduce((s, t) => s + Number(t.amount), 0)
        );

        months.push({
          month: d.toLocaleDateString("pt-BR", { month: "short" }),
          income,
          expenses,
        });
      }

      setData(months);
    }
    fetchData();
  }, [userId, supabase]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Receita vs Gastos</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" />
            <YAxis tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`} />
            <Tooltip
              formatter={(value) => formatCurrency(Number(value))}
              labelStyle={{ color: "#333" }}
            />
            <Legend />
            <Bar dataKey="income" name="Receita" fill="#0EA5E9" radius={[4, 4, 0, 0]} />
            <Bar dataKey="expenses" name="Gastos" fill="#EF4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
