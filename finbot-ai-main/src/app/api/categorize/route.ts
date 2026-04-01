import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { categorizeTransactions } from "@/lib/ai/categorize";

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const body = await request.json();
    const { transaction_ids } = body as { transaction_ids?: string[] };

    // Fetch uncategorized transactions
    let query = supabase
      .from("transactions")
      .select("id, date, amount, description, type, external_id")
      .eq("user_id", user.id)
      .is("category_id", null);

    if (transaction_ids?.length) {
      query = query.in("id", transaction_ids);
    }

    const { data: transactions, error: txError } = await query;
    if (txError) throw txError;
    if (!transactions?.length) {
      return NextResponse.json({ categorized: 0, failed: 0, results: [] });
    }

    // Fetch user rules
    const { data: rules } = await supabase
      .from("category_rules")
      .select("pattern, category_id, categories(name)")
      .eq("user_id", user.id);

    const userRules = (rules || []).map((r) => ({
      pattern: r.pattern,
      category_id: r.category_id,
      category_name: (r.categories as unknown as { name: string })?.name || "",
    }));

    // Fetch categories
    const { data: categories } = await supabase
      .from("categories")
      .select("id, name")
      .or(`user_id.is.null,user_id.eq.${user.id}`);

    const rawTransactions = transactions.map((t) => ({
      date: t.date,
      amount: Number(t.amount),
      description: t.description,
      type: t.type as string,
      external_id: t.external_id || t.id,
    }));

    const results = await categorizeTransactions(
      rawTransactions,
      userRules,
      categories || []
    );

    // Update transactions with categories
    let categorized = 0;
    let failed = 0;

    for (const result of results) {
      const category = (categories || []).find((c) => c.name === result.category_name);
      if (!category) {
        failed++;
        continue;
      }

      const tx = transactions.find(
        (t) => (t.external_id || t.id) === result.external_id
      );
      if (!tx) {
        failed++;
        continue;
      }

      const { error } = await supabase
        .from("transactions")
        .update({
          category_id: category.id,
          clean_description: result.clean_description,
          confidence: result.confidence,
          is_recurring: result.is_recurring,
        })
        .eq("id", tx.id);

      if (error) failed++;
      else categorized++;
    }

    return NextResponse.json({
      categorized,
      failed,
      results: results.map((r) => ({
        external_id: r.external_id,
        category_name: r.category_name,
        confidence: r.confidence,
      })),
    });
  } catch (error) {
    console.error("Categorize error:", error);
    return NextResponse.json(
      { error: "Erro ao categorizar" },
      { status: 500 }
    );
  }
}
