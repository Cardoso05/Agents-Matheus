"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatCurrency } from "@/lib/utils/currency";
import { CATEGORY_GROUPS } from "@/lib/constants/categories";
import { Pencil, Check, X } from "lucide-react";

interface BudgetGroup {
  group: string;
  label: string;
  color: string;
  type: string;
  spent: number;
  limit: number;
}

export default function BudgetPage() {
  const [groups, setGroups] = useState<BudgetGroup[]>([]);
  const [income, setIncome] = useState(0);
  const [loading, setLoading] = useState(true);
  const [editingGroup, setEditingGroup] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [customLimits, setCustomLimits] = useState<Record<string, number>>({});
  const supabase = createClient();

  useEffect(() => {
    // Load saved custom limits from localStorage
    const saved = localStorage.getItem("finbot-budget-limits");
    if (saved) {
      setCustomLimits(JSON.parse(saved));
    }
  }, []);

  useEffect(() => {
    async function fetchData() {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split("T")[0];

      // Last 3 months income average
      const threeMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 3, 1).toISOString().split("T")[0];
      const { data: incomeTxs } = await supabase
        .from("transactions")
        .select("amount")
        .eq("type", "income")
        .gte("date", threeMonthsAgo)
        .lte("date", end);

      const totalIncome3m = (incomeTxs || []).reduce((s, t) => s + Number(t.amount), 0);
      const avgIncome = totalIncome3m / 3 || 0;
      setIncome(avgIncome);

      // Current month expenses by category group
      const { data: expenses } = await supabase
        .from("transactions")
        .select("amount, category:categories(group_name)")
        .eq("type", "expense")
        .gte("date", start)
        .lte("date", end);

      const groupSpending = new Map<string, number>();
      for (const tx of expenses || []) {
        const group = (tx.category as unknown as { group_name: string })?.group_name || "outros";
        groupSpending.set(group, (groupSpending.get(group) || 0) + Math.abs(Number(tx.amount)));
      }

      // 50-30-20 rule
      const necessities = avgIncome * 0.5;
      const wants = avgIncome * 0.3;
      const savings = avgIncome * 0.2;

      const budgetGroups: BudgetGroup[] = Object.entries(CATEGORY_GROUPS)
        .filter(([key]) => key !== "renda")
        .map(([key, group]) => {
          let defaultLimit: number;
          const groupConfig = group as { type: string };
          if (groupConfig.type === "necessity") {
            const necessityGroups = Object.entries(CATEGORY_GROUPS).filter(
              ([, g]) => (g as { type: string }).type === "necessity"
            ).length;
            defaultLimit = necessities / necessityGroups;
          } else if (groupConfig.type === "saving") {
            defaultLimit = savings;
          } else {
            const wantGroups = Object.entries(CATEGORY_GROUPS).filter(
              ([, g]) => (g as { type: string }).type === "want"
            ).length;
            defaultLimit = wants / wantGroups;
          }

          return {
            group: key,
            label: group.label,
            color: group.color,
            type: groupConfig.type,
            spent: groupSpending.get(key) || 0,
            limit: customLimits[key] ?? defaultLimit,
          };
        })
        .sort((a, b) => b.spent - a.spent);

      setGroups(budgetGroups);
      setLoading(false);
    }
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customLimits]);

  function startEditing(group: string, currentLimit: number) {
    setEditingGroup(group);
    setEditValue(currentLimit.toFixed(0));
  }

  function saveLimit(group: string) {
    const newValue = parseFloat(editValue);
    if (isNaN(newValue) || newValue < 0) return;

    const updated = { ...customLimits, [group]: newValue };
    setCustomLimits(updated);
    localStorage.setItem("finbot-budget-limits", JSON.stringify(updated));
    setEditingGroup(null);

    // Update the group in state immediately
    setGroups((prev) =>
      prev.map((g) => (g.group === group ? { ...g, limit: newValue } : g))
    );
  }

  function resetLimits() {
    setCustomLimits({});
    localStorage.removeItem("finbot-budget-limits");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Orçamento</h1>
          <p className="text-muted-foreground">
            Baseado na regra 50-30-20 com renda média de {formatCurrency(income)}
          </p>
        </div>
        {Object.keys(customLimits).length > 0 && (
          <Button variant="outline" size="sm" onClick={resetLimits}>
            Resetar para 50-30-20
          </Button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-muted-foreground">Necessidades (50%)</p>
            <p className="text-xl font-bold text-indigo-600">{formatCurrency(income * 0.5)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-muted-foreground">Desejos (30%)</p>
            <p className="text-xl font-bold text-pink-600">{formatCurrency(income * 0.3)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-sm text-muted-foreground">Poupança (20%)</p>
            <p className="text-xl font-bold text-green-600">{formatCurrency(income * 0.2)}</p>
          </CardContent>
        </Card>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse bg-slate-100 rounded" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => {
            const percent = group.limit > 0 ? (group.spent / group.limit) * 100 : 0;
            const status =
              percent > 100 ? "text-red-600" : percent > 80 ? "text-yellow-600" : "text-green-600";
            const isEditing = editingGroup === group.group;

            return (
              <Card key={group.group}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: group.color }}
                      />
                      <span className="font-medium text-sm">{group.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {isEditing ? (
                        <div className="flex items-center gap-1">
                          <span className="text-sm text-muted-foreground">
                            {formatCurrency(group.spent)} /
                          </span>
                          <Input
                            className="w-28 h-7 text-sm"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveLimit(group.group);
                              if (e.key === "Escape") setEditingGroup(null);
                            }}
                            autoFocus
                          />
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7"
                            onClick={() => saveLimit(group.group)}
                          >
                            <Check className="h-3 w-3 text-green-600" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7"
                            onClick={() => setEditingGroup(null)}
                          >
                            <X className="h-3 w-3 text-red-600" />
                          </Button>
                        </div>
                      ) : (
                        <>
                          <span className={`text-sm font-semibold ${status}`}>
                            {formatCurrency(group.spent)} / {formatCurrency(group.limit)}
                          </span>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7"
                            onClick={() => startEditing(group.group, group.limit)}
                          >
                            <Pencil className="h-3 w-3 text-muted-foreground" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  <Progress
                    value={Math.min(100, percent)}
                    className={percent > 100 ? "[&>div]:bg-red-500" : percent > 80 ? "[&>div]:bg-yellow-500" : ""}
                  />
                  {percent > 100 && (
                    <p className="text-xs text-red-600 mt-1">
                      Excedido em {formatCurrency(group.spent - group.limit)}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
