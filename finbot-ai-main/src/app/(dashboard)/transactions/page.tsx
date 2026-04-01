"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatCurrency } from "@/lib/utils/currency";
import { formatDate } from "@/lib/utils/date";
import { Search, Filter, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Transaction {
  id: string;
  date: string;
  description: string;
  clean_description: string | null;
  amount: number;
  type: string;
  confidence: number;
  is_confirmed: boolean;
  category: { id: string; name: string; color: string } | null;
}

interface Category {
  id: string;
  name: string;
  color: string;
}

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [categorizing, setCategorizing] = useState(false);
  const supabase = createClient();

  async function fetchData() {
    const [txResult, catResult] = await Promise.all([
      supabase
        .from("transactions")
        .select("id, date, description, clean_description, amount, type, confidence, is_confirmed, category:categories(id, name, color)")
        .order("date", { ascending: false })
        .limit(100),
      supabase
        .from("categories")
        .select("id, name, color")
        .order("name"),
    ]);

    const txData = (txResult.data as unknown as Transaction[]) || [];
    setTransactions(txData);
    setCategories((catResult.data as Category[]) || []);
    setLoading(false);

    // Auto-categorizar se há transações sem categoria
    const uncategorized = txData.filter((tx) => !tx.category);
    if (uncategorized.length > 0) {
      await runCategorize();
    }
  }

  async function runCategorize() {
    setCategorizing(true);
    try {
      const res = await fetch("/api/categorize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.categorized > 0) {
          toast.success(`${data.categorized} lançamentos categorizados pela IA!`);
          // Recarregar transações com categorias atualizadas
          const { data: refreshed } = await supabase
            .from("transactions")
            .select("id, date, description, clean_description, amount, type, confidence, is_confirmed, category:categories(id, name, color)")
            .order("date", { ascending: false })
            .limit(100);
          setTransactions((refreshed as unknown as Transaction[]) || []);
        }
      }
    } catch {
      console.error("Erro ao categorizar");
    } finally {
      setCategorizing(false);
    }
  }

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function updateCategory(txId: string, categoryId: string) {
    await supabase
      .from("transactions")
      .update({ category_id: categoryId, is_confirmed: true })
      .eq("id", txId);

    setTransactions((prev) =>
      prev.map((tx) =>
        tx.id === txId
          ? { ...tx, category: categories.find((c) => c.id === categoryId) || null, is_confirmed: true }
          : tx
      )
    );
  }

  const filtered = transactions.filter((tx) => {
    const matchSearch =
      !search ||
      tx.description.toLowerCase().includes(search.toLowerCase()) ||
      tx.clean_description?.toLowerCase().includes(search.toLowerCase());
    const matchType = typeFilter === "all" || tx.type === typeFilter;
    return matchSearch && matchType;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Lançamentos</h1>
          <p className="text-muted-foreground">Todos os seus lançamentos importados</p>
        </div>
        {transactions.some((tx) => !tx.category) && (
          <Button onClick={runCategorize} disabled={categorizing} variant="outline">
            {categorizing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4 mr-2" />
            )}
            {categorizing ? "Categorizando..." : "Categorizar com IA"}
          </Button>
        )}
      </div>
      {categorizing && (
        <div className="flex items-center gap-2 text-sm text-sky-600 bg-sky-50 px-4 py-2 rounded-lg">
          <Loader2 className="h-4 w-4 animate-spin" />
          Categorizando lançamentos com IA... isso pode levar alguns segundos.
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar lançamentos..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-40">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="income">Receitas</SelectItem>
                <SelectItem value="expense">Despesas</SelectItem>
                <SelectItem value="transfer">Transferências</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 animate-pulse bg-slate-100 rounded" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data</TableHead>
                    <TableHead>Descrição</TableHead>
                    <TableHead>Categoria</TableHead>
                    <TableHead className="text-right">Valor</TableHead>
                    <TableHead>Confiança</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((tx) => (
                    <TableRow key={tx.id}>
                      <TableCell className="text-sm">{formatDate(tx.date)}</TableCell>
                      <TableCell className="text-sm max-w-xs truncate">
                        {tx.clean_description || tx.description}
                      </TableCell>
                      <TableCell>
                        <Select
                          value={tx.category?.id || ""}
                          onValueChange={(val) => updateCategory(tx.id, val)}
                        >
                          <SelectTrigger className="w-40 h-8">
                            <SelectValue placeholder="Selecionar..." />
                          </SelectTrigger>
                          <SelectContent>
                            {categories.map((cat) => (
                              <SelectItem key={cat.id} value={cat.id}>
                                <div className="flex items-center gap-2">
                                  <div
                                    className="w-2 h-2 rounded-full"
                                    style={{ backgroundColor: cat.color }}
                                  />
                                  {cat.name}
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell
                        className={`text-sm text-right font-medium ${
                          tx.type === "income" ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {formatCurrency(Math.abs(tx.amount))}
                      </TableCell>
                      <TableCell>
                        {tx.is_confirmed ? (
                          <Badge variant="default" className="text-xs">Confirmado</Badge>
                        ) : tx.confidence > 0 ? (
                          <Badge variant="secondary" className="text-xs">
                            {(tx.confidence * 100).toFixed(0)}%
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-xs">Pendente</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {filtered.length === 0 && (
                <p className="text-center text-muted-foreground py-8 text-sm">
                  Nenhum lançamento encontrado
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
