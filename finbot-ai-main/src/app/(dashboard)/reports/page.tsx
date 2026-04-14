"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils/currency";
import { FileText, Loader2, TrendingUp } from "lucide-react";
import { toast } from "sonner";

interface Report {
  id: string;
  month: string;
  health_score: number;
  total_income: number;
  total_expenses: number;
  total_balance: number;
  summary: {
    highlights: string[];
    concerns: string[];
    improvements: string[];
  };
  recommendations: string[];
  created_at: string;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const supabase = createClient();

  useEffect(() => {
    async function fetchReports() {
      const { data } = await supabase
        .from("reports")
        .select("*")
        .order("month", { ascending: false });
      setReports((data as Report[]) || []);
      setLoading(false);
    }
    fetchReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function generateReport() {
    setGenerating(true);
    try {
      const res = await fetch("/api/reports/monthly", { method: "POST" });
      if (!res.ok) throw new Error("Erro ao gerar relatório");

      const data = await res.json();
      toast.success("Relatório gerado!");
      setReports((prev) => [data, ...prev]);
    } catch {
      toast.error("Erro ao gerar relatório");
    } finally {
      setGenerating(false);
    }
  }

  function getScoreColor(score: number) {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Relatórios</h1>
          <p className="text-muted-foreground">Análise mensal das suas finanças</p>
        </div>
        <Button onClick={generateReport} disabled={generating}>
          {generating ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <FileText className="h-4 w-4 mr-2" />
          )}
          Gerar Relatório
        </Button>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-48 animate-pulse bg-slate-100 rounded-lg" />
          ))}
        </div>
      ) : reports.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
            <TrendingUp className="h-12 w-12 text-slate-300" />
            <p className="text-muted-foreground">Nenhum relatório gerado</p>
            <Button variant="outline" onClick={generateReport}>
              Gerar primeiro relatório
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {reports.map((report) => (
            <Card key={report.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    {new Date(report.month).toLocaleDateString("pt-BR", {
                      month: "long",
                      year: "numeric",
                    })}
                  </CardTitle>
                  {report.health_score !== null && (
                    <div className="text-center">
                      <p className="text-xs text-muted-foreground">Score</p>
                      <p className={`text-2xl font-bold ${getScoreColor(report.health_score)}`}>
                        {report.health_score}
                      </p>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Renda</p>
                    <p className="font-semibold text-green-600">
                      {formatCurrency(Number(report.total_income))}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Gastos</p>
                    <p className="font-semibold text-red-600">
                      {formatCurrency(Number(report.total_expenses))}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Saldo</p>
                    <p className={`font-semibold ${Number(report.total_balance) >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {formatCurrency(Number(report.total_balance))}
                    </p>
                  </div>
                </div>

                {report.summary?.highlights?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2 text-green-700">Destaques</p>
                    <div className="space-y-1">
                      {report.summary.highlights.map((h, i) => (
                        <p key={i} className="text-sm text-muted-foreground">✅ {h}</p>
                      ))}
                    </div>
                  </div>
                )}

                {report.summary?.concerns?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2 text-yellow-700">Preocupações</p>
                    <div className="space-y-1">
                      {report.summary.concerns.map((c, i) => (
                        <p key={i} className="text-sm text-muted-foreground">⚠️ {c}</p>
                      ))}
                    </div>
                  </div>
                )}

                {report.summary?.improvements?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2 text-blue-700">Melhorias</p>
                    <div className="space-y-1">
                      {report.summary.improvements.map((m, i) => (
                        <p key={i} className="text-sm text-muted-foreground">💡 {m}</p>
                      ))}
                    </div>
                  </div>
                )}

                {report.recommendations?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Recomendações</p>
                    <div className="space-y-1">
                      {report.recommendations.map((rec, i) => (
                        <p key={i} className="text-sm text-muted-foreground">
                          • {rec}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
