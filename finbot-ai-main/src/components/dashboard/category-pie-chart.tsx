"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { formatCurrency } from "@/lib/utils/currency";

interface CategoryData {
  name: string;
  value: number;
  color: string;
}

export function CategoryPieChart({ userId }: { userId: string }) {
  const [data, setData] = useState<CategoryData[]>([]);
  const supabase = createClient();

  useEffect(() => {
    async function fetchData() {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split("T")[0];

      const { data: txs } = await supabase
        .from("transactions")
        .select("amount, category:categories(name, color)")
        .eq("user_id", userId)
        .eq("type", "expense")
        .gte("date", start)
        .lte("date", end);

      const map = new Map<string, { total: number; color: string }>();
      for (const tx of txs || []) {
        const cat = tx.category as unknown as { name: string; color: string } | null;
        const name = cat?.name || "Sem categoria";
        const color = cat?.color || "#6B7280";
        const existing = map.get(name) || { total: 0, color };
        existing.total += Math.abs(Number(tx.amount));
        map.set(name, existing);
      }

      const sorted = Array.from(map.entries())
        .map(([name, { total, color }]) => ({ name, value: total, color }))
        .sort((a, b) => b.value - a.value)
        .slice(0, 8);

      setData(sorted);
    }
    fetchData();
  }, [userId, supabase]);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Gastos por Categoria</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">
          Nenhum gasto registrado este mês
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Gastos por Categoria</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => formatCurrency(Number(value))} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
