"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/utils/currency";
import { formatDate } from "@/lib/utils/date";
import Link from "next/link";

interface RecentTx {
  id: string;
  date: string;
  description: string;
  clean_description: string | null;
  amount: number;
  type: string;
  category: { name: string; color: string; icon: string } | null;
}

export function RecentTransactions({ userId }: { userId: string }) {
  const [transactions, setTransactions] = useState<RecentTx[]>([]);
  const supabase = createClient();

  useEffect(() => {
    async function fetchData() {
      const { data } = await supabase
        .from("transactions")
        .select("id, date, description, clean_description, amount, type, category:categories(name, color, icon)")
        .eq("user_id", userId)
        .order("date", { ascending: false })
        .limit(10);

      setTransactions((data as unknown as RecentTx[]) || []);
    }
    fetchData();
  }, [userId, supabase]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Lançamentos Recentes</CardTitle>
        <Link href="/transactions" className="text-sm text-sky-500 hover:underline">
          Ver todos
        </Link>
      </CardHeader>
      <CardContent>
        {transactions.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            Nenhum lançamento encontrado. Faça upload de um extrato para começar.
          </p>
        ) : (
          <div className="space-y-3">
            {transactions.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
                    style={{ backgroundColor: tx.category?.color || "#6B7280" }}
                  >
                    {(tx.category?.name || "?")[0]}
                  </div>
                  <div>
                    <p className="text-sm font-medium">
                      {tx.clean_description || tx.description}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {formatDate(tx.date)}
                      </span>
                      {tx.category && (
                        <Badge variant="secondary" className="text-xs">
                          {tx.category.name}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
                <span
                  className={`text-sm font-semibold ${
                    tx.type === "income" ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {tx.type === "income" ? "+" : "-"}
                  {formatCurrency(Math.abs(tx.amount))}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
