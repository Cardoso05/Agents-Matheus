import { RawTransaction } from "./index";
import { generateExternalId } from "@/lib/utils/dedup";

export async function parsePDF(file: Buffer): Promise<RawTransaction[]> {
  // Dynamic import to avoid pdf-parse loading test files at module scope
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const pdfParse = require("pdf-parse");
  const result = await pdfParse(file);
  const text: string = result.text;

  const lines = text
    .split("\n")
    .map((l: string) => l.trim())
    .filter(Boolean);

  const transactions: RawTransaction[] = [];

  // Pattern: DD/MM/YYYY ... description ... -1.234,56 or 1.234,56
  const dateAmountRegex =
    /^(\d{2}\/\d{2}\/\d{4})\s+(.+?)\s+(-?\s*[\d.,]+)\s*$/;

  // Alternate pattern: DD/MM ... description ... amount (no year)
  const shortDateRegex =
    /^(\d{2}\/\d{2})\s+(.+?)\s+(-?\s*[\d.,]+)\s*$/;

  const currentYear = new Date().getFullYear();

  for (const line of lines) {
    let match = dateAmountRegex.exec(line);
    let dateStr: string | null = null;
    let description: string | null = null;
    let rawAmount: string | null = null;

    if (match) {
      dateStr = match[1];
      description = match[2];
      rawAmount = match[3];
    } else {
      match = shortDateRegex.exec(line);
      if (match) {
        dateStr = `${match[1]}/${currentYear}`;
        description = match[2];
        rawAmount = match[3];
      }
    }

    if (!dateStr || !description || !rawAmount) continue;

    const amount = parseAmount(rawAmount);
    if (isNaN(amount) || amount === 0) continue;

    const date = parseDate(dateStr);
    if (!date) continue;

    transactions.push({
      date,
      amount,
      description: description.trim(),
      type: amount >= 0 ? "income" : "expense",
      bank_slug: "pdf",
      external_id: generateExternalId(date, amount, description),
    });
  }

  if (transactions.length === 0) {
    throw new Error(
      "Nenhuma transação encontrada no PDF. Verifique se o extrato está em formato texto (não imagem)."
    );
  }

  return transactions;
}

function parseAmount(raw: string): number {
  const cleaned = raw.replace(/\s/g, "");
  // Brazilian format: 1.234,56 → 1234.56
  const normalized = cleaned.replace(/\./g, "").replace(",", ".");
  return parseFloat(normalized);
}

function parseDate(dateStr: string): string | null {
  const parts = dateStr.split("/");
  if (parts.length < 2) return null;

  const day = parts[0].padStart(2, "0");
  const month = parts[1].padStart(2, "0");
  const year = parts[2] || String(new Date().getFullYear());

  const y = year.length === 2 ? `20${year}` : year;

  if (parseInt(month) < 1 || parseInt(month) > 12) return null;
  if (parseInt(day) < 1 || parseInt(day) > 31) return null;

  return `${y}-${month}-${day}`;
}
