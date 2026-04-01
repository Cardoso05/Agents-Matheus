import Anthropic from "@anthropic-ai/sdk";
import { CHAT_SYSTEM_PROMPT, RESCUE_MODE_INSTRUCTIONS, EMERGENCY_MODE_INSTRUCTIONS } from "./prompts";

interface ChatContext {
  financialSummary: string;
  debtsContext: string;
  recentTransactions: string;
  isRescueMode?: boolean;
  isEmergency?: boolean;
}

const EMERGENCY_KEYWORDS = [
  "não tenho dinheiro",
  "nao tenho dinheiro",
  "dinheiro não fecha",
  "dinheiro nao fecha",
  "conta vencida",
  "sem dinheiro",
  "dinheiro curto",
  "não consigo pagar",
  "nao consigo pagar",
  "atrasado",
  "atrasada",
  "negativado",
  "nome sujo",
  "cobrança",
  "cobranças",
  "desesperado",
  "desespero",
  "socorro",
  "ajuda urgente",
  "emergência",
  "emergencia",
  "não sei o que fazer",
  "estou ferrado",
  "falido",
];

export function detectEmergency(messages: { role: string; content: string }[]): boolean {
  const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
  if (!lastUserMessage) return false;
  const text = lastUserMessage.content.toLowerCase();
  return EMERGENCY_KEYWORDS.some((kw) => text.includes(kw));
}

export function buildChatSystemPrompt(context: ChatContext): string {
  let rescueInstructions = "";

  if (context.isEmergency) {
    rescueInstructions = EMERGENCY_MODE_INSTRUCTIONS;
  } else if (context.isRescueMode) {
    rescueInstructions = RESCUE_MODE_INSTRUCTIONS;
  }

  return CHAT_SYSTEM_PROMPT
    .replace("{rescue_mode_instructions}", rescueInstructions)
    .replace("{financial_context}", context.financialSummary)
    .replace("{debts_context}", context.debtsContext)
    .replace("{recent_transactions}", context.recentTransactions);
}

export async function* streamChatResponse(
  messages: { role: "user" | "assistant"; content: string }[],
  systemPrompt: string
): AsyncGenerator<string> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    yield "Erro: ANTHROPIC_API_KEY não configurada. Configure em .env.local";
    return;
  }

  const client = new Anthropic({ apiKey });

  const stream = await client.messages.stream({
    model: "claude-sonnet-4-20250514",
    max_tokens: 2048,
    system: systemPrompt,
    messages,
  });

  for await (const event of stream) {
    if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
      yield event.delta.text;
    }
  }
}
