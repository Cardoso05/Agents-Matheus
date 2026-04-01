import Anthropic from "@anthropic-ai/sdk";
import { MONTHLY_REPORT_PROMPT } from "./prompts";

interface MonthData {
  month: string;
  totalIncome: number;
  totalExpenses: number;
  categoryBreakdown: { name: string; total: number }[];
  previousMonth: { income: number; expenses: number } | null;
  debtProgress: { total: number; paid: number } | null;
}

interface ReportResult {
  health_score: number;
  summary: {
    highlights: string[];
    concerns: string[];
    improvements: string[];
  };
  recommendations: string[];
}

function extractJSON(text: string): string {
  let cleaned = text.trim();
  if (cleaned.startsWith("```json")) {
    cleaned = cleaned.slice(7);
  } else if (cleaned.startsWith("```")) {
    cleaned = cleaned.slice(3);
  }
  if (cleaned.endsWith("```")) {
    cleaned = cleaned.slice(0, -3);
  }
  return cleaned.trim();
}

function computeFallbackReport(data: MonthData): ReportResult {
  const balance = data.totalIncome - data.totalExpenses;
  const savingsRate = data.totalIncome > 0 ? (balance / data.totalIncome) * 100 : 0;

  let score: number;
  if (savingsRate >= 20) score = 85;
  else if (savingsRate >= 10) score = 70;
  else if (savingsRate >= 0) score = 50;
  else score = 30;

  const topExpenses = data.categoryBreakdown
    .sort((a, b) => b.total - a.total)
    .slice(0, 3)
    .map((c) => c.name);

  return {
    health_score: score,
    summary: {
      highlights: [
        `Renda total de R$ ${data.totalIncome.toFixed(2)}`,
        balance > 0
          ? `Saldo positivo de R$ ${balance.toFixed(2)}`
          : `Gastos excederam a renda em R$ ${Math.abs(balance).toFixed(2)}`,
      ],
      concerns: topExpenses.length > 0
        ? [`Maiores gastos: ${topExpenses.join(", ")}`]
        : [],
      improvements: ["Configure a ANTHROPIC_API_KEY para relatórios detalhados com IA"],
    },
    recommendations: [
      "Revise seus maiores gastos do mês",
      "Tente poupar pelo menos 20% da renda",
      "Acompanhe seus gastos semanalmente",
    ],
  };
}

export async function generateMonthlyReport(
  data: MonthData
): Promise<ReportResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return computeFallbackReport(data);
  }

  try {
    const client = new Anthropic({ apiKey });
    const prompt = MONTHLY_REPORT_PROMPT.replace(
      "{month_data}",
      JSON.stringify(data, null, 2)
    );

    const response = await client.messages.create({
      model: "claude-sonnet-4-20250514",
      max_tokens: 2048,
      messages: [{ role: "user", content: prompt }],
    });

    const text = response.content[0].type === "text" ? response.content[0].text : "{}";
    const cleaned = extractJSON(text);

    try {
      const parsed = JSON.parse(cleaned) as ReportResult;
      if (typeof parsed.health_score !== "number" || !parsed.summary || !parsed.recommendations) {
        return computeFallbackReport(data);
      }
      return parsed;
    } catch {
      console.error("Failed to parse AI report response:", text);
      return computeFallbackReport(data);
    }
  } catch (error) {
    console.error("AI report generation error:", error);
    return computeFallbackReport(data);
  }
}
