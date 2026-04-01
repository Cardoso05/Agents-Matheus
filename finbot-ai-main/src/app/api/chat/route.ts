import { NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { buildChatSystemPrompt, streamChatResponse, detectEmergency } from "@/lib/ai/chat";
import { formatCurrency } from "@/lib/utils/currency";

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return new Response("Não autorizado", { status: 401 });
    }

    const body = await request.json();
    const { messages } = body as {
      messages: { role: "user" | "assistant"; content: string }[];
    };

    // Build financial context
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
      .toISOString()
      .split("T")[0];
    const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0)
      .toISOString()
      .split("T")[0];

    // Check rescue mode and emergency
    const { data: profile } = await supabase
      .from("profiles")
      .select("is_rescue_mode")
      .eq("id", user.id)
      .single();

    const isRescueMode = profile?.is_rescue_mode || false;
    const isEmergency = detectEmergency(messages);

    const [txResult, debtsResult, recentResult] = await Promise.all([
      supabase
        .from("transactions")
        .select("amount, type, category:categories(name)")
        .eq("user_id", user.id)
        .gte("date", startOfMonth)
        .lte("date", endOfMonth),
      supabase
        .from("debts")
        .select("name, current_balance, interest_rate, minimum_payment")
        .eq("user_id", user.id)
        .eq("status", "active"),
      supabase
        .from("transactions")
        .select("date, description, clean_description, amount, type, category:categories(name)")
        .eq("user_id", user.id)
        .order("date", { ascending: false })
        .limit(20),
    ]);

    const income = (txResult.data || [])
      .filter((t) => t.type === "income")
      .reduce((s, t) => s + Number(t.amount), 0);
    const expenses = Math.abs(
      (txResult.data || [])
        .filter((t) => t.type === "expense")
        .reduce((s, t) => s + Number(t.amount), 0)
    );

    // Build category breakdown
    const catMap = new Map<string, number>();
    for (const tx of txResult.data || []) {
      if (tx.type === "expense") {
        const cat = (tx.category as unknown as { name: string })?.name || "Outros";
        catMap.set(cat, (catMap.get(cat) || 0) + Math.abs(Number(tx.amount)));
      }
    }
    const topCategories = Array.from(catMap.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, total]) => `${name}: ${formatCurrency(total)}`)
      .join("\n");

    const financialSummary = `Mês atual:
- Renda: ${formatCurrency(income)}
- Gastos: ${formatCurrency(expenses)}
- Saldo: ${formatCurrency(income - expenses)}

Top 5 categorias de gasto:
${topCategories || "Nenhum gasto registrado"}`;

    const debtsContext = (debtsResult.data || [])
      .map(
        (d) =>
          `- ${d.name}: Saldo ${formatCurrency(Number(d.current_balance))}, Juros ${(Number(d.interest_rate) * 100).toFixed(2)}%/mês, Mínimo ${formatCurrency(Number(d.minimum_payment))}`
      )
      .join("\n") || "Nenhuma dívida cadastrada";

    const recentTxText = (recentResult.data || [])
      .map(
        (t) =>
          `${t.date} | ${t.clean_description || t.description} | ${formatCurrency(Number(t.amount))} | ${(t.category as unknown as { name: string })?.name || "Sem categoria"}`
      )
      .join("\n") || "Nenhuma transação recente";

    const systemPrompt = buildChatSystemPrompt({
      financialSummary,
      debtsContext,
      recentTransactions: recentTxText,
      isRescueMode,
      isEmergency,
    });

    // Stream response
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        try {
          for await (const text of streamChatResponse(messages, systemPrompt)) {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ text })}\n\n`));
          }
          controller.enqueue(encoder.encode("data: [DONE]\n\n"));
          controller.close();
        } catch (error) {
          console.error("Chat stream error:", error);
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ text: "\n\nDesculpe, ocorreu um erro. Tente novamente." })}\n\n`
            )
          );
          controller.enqueue(encoder.encode("data: [DONE]\n\n"));
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (error) {
    console.error("Chat error:", error);
    return new Response("Erro interno", { status: 500 });
  }
}
