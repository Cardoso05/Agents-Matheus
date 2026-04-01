import Anthropic from "@anthropic-ai/sdk";
import { CATEGORIZE_PROMPT } from "./prompts";

interface RawTransaction {
  date: string;
  amount: number;
  description: string;
  type: string;
  external_id: string;
}

interface CategorizedResult {
  external_id: string;
  category_name: string;
  clean_description: string;
  confidence: number;
  is_recurring: boolean;
}

interface CategoryRule {
  pattern: string;
  category_id: string;
  category_name: string;
}

const GLOBAL_RULES: Record<string, string> = {
  uber: "Uber/99",
  "99app": "Uber/99",
  "99 pop": "Uber/99",
  netflix: "Streaming",
  spotify: "Streaming",
  "amazon prime": "Streaming",
  "disney+": "Streaming",
  "hbo max": "Streaming",
  youtube: "Streaming",
  ifood: "Delivery",
  rappi: "Delivery",
  "zé delivery": "Delivery",
  "posto": "Combustível",
  shell: "Combustível",
  ipiranga: "Combustível",
  farmacia: "Farmácia",
  drogasil: "Farmácia",
  droga: "Farmácia",
  supermercado: "Supermercado",
  carrefour: "Supermercado",
  "pao de acucar": "Supermercado",
  assai: "Supermercado",
  atacadao: "Supermercado",
  "smart fit": "Academia",
  "bio ritmo": "Academia",
};

export async function categorizeTransactions(
  transactions: RawTransaction[],
  userRules: CategoryRule[],
  categories: { name: string }[]
): Promise<CategorizedResult[]> {
  const results: CategorizedResult[] = [];
  const remaining: RawTransaction[] = [];

  // Step 1: Apply user rules
  for (const tx of transactions) {
    const desc = tx.description.toLowerCase();
    const rule = userRules.find((r) => desc.includes(r.pattern.toLowerCase()));
    if (rule) {
      results.push({
        external_id: tx.external_id,
        category_name: rule.category_name,
        clean_description: tx.description,
        confidence: 0.95,
        is_recurring: false,
      });
    } else {
      remaining.push(tx);
    }
  }

  // Step 2: Apply global rules
  const stillRemaining: RawTransaction[] = [];
  for (const tx of remaining) {
    const desc = tx.description.toLowerCase();
    let matched = false;
    for (const [keyword, category] of Object.entries(GLOBAL_RULES)) {
      if (desc.includes(keyword)) {
        results.push({
          external_id: tx.external_id,
          category_name: category,
          clean_description: tx.description,
          confidence: 0.85,
          is_recurring: false,
        });
        matched = true;
        break;
      }
    }
    if (!matched) stillRemaining.push(tx);
  }

  // Step 3: AI classification for remaining
  if (stillRemaining.length > 0) {
    const aiResults = await classifyWithAI(stillRemaining, categories);
    results.push(...aiResults);
  }

  return results;
}

async function classifyWithAI(
  transactions: RawTransaction[],
  categories: { name: string }[]
): Promise<CategorizedResult[]> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return transactions.map((tx) => ({
      external_id: tx.external_id,
      category_name: tx.amount >= 0 ? "Outros (Receita)" : "Outros (Despesa)",
      clean_description: tx.description,
      confidence: 0.3,
      is_recurring: false,
    }));
  }

  const client = new Anthropic({ apiKey });
  const batches = [];

  // Batch in groups of 50
  for (let i = 0; i < transactions.length; i += 50) {
    batches.push(transactions.slice(i, i + 50));
  }

  const allResults: CategorizedResult[] = [];

  for (const batch of batches) {
    const prompt = CATEGORIZE_PROMPT
      .replace("{categories_list}", categories.map((c) => c.name).join(", "))
      .replace(
        "{transactions_json}",
        JSON.stringify(
          batch.map((t) => ({
            external_id: t.external_id,
            date: t.date,
            amount: t.amount,
            description: t.description,
          }))
        )
      );

    try {
      const response = await client.messages.create({
        model: "claude-sonnet-4-20250514",
        max_tokens: 4096,
        messages: [{ role: "user", content: prompt }],
      });

      const text = response.content[0].type === "text" ? response.content[0].text : "";
      const parsed = JSON.parse(text) as CategorizedResult[];
      allResults.push(...parsed);
    } catch (error) {
      console.error("AI classification error:", error);
      // Fallback for failed batch
      allResults.push(
        ...batch.map((tx) => ({
          external_id: tx.external_id,
          category_name: tx.amount >= 0 ? "Outros (Receita)" : "Outros (Despesa)",
          clean_description: tx.description,
          confidence: 0.3,
          is_recurring: false,
        }))
      );
    }
  }

  return allResults;
}
