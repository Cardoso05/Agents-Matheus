import { RawTransaction } from "./index";
import { generateExternalId } from "@/lib/utils/dedup";

export function parseCSV(file: Buffer): RawTransaction[] {
  const content = file.toString("utf-8");
  const lines = content.trim().split("\n");

  if (lines.length < 2) throw new Error("Arquivo CSV vazio ou inválido");

  const header = lines[0].toLowerCase();
  const delimiter = header.includes(";") ? ";" : ",";
  const headers = header.split(delimiter).map((h) => h.trim().replace(/"/g, ""));

  // Detect bank by header pattern
  if (headers.includes("category") || headers.includes("title")) {
    return parseNubankCSV(lines, delimiter);
  }

  return parseGenericCSV(lines, delimiter, headers);
}

function parseNubankCSV(lines: string[], delimiter: string): RawTransaction[] {
  const transactions: RawTransaction[] = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const cols = line.split(delimiter).map((c) => c.trim().replace(/"/g, ""));
    const [date, , title, amount] = cols;

    if (!date || !amount) continue;

    const parsedAmount = parseFloat(amount.replace(",", "."));
    if (isNaN(parsedAmount)) continue;

    const tx: RawTransaction = {
      date: parseDate(date),
      amount: parsedAmount,
      description: title || "Sem descrição",
      type: parsedAmount >= 0 ? "income" : "expense",
      bank_slug: "nubank",
      external_id: generateExternalId(date, parsedAmount, title),
    };
    transactions.push(tx);
  }

  return transactions;
}

function parseGenericCSV(
  lines: string[],
  delimiter: string,
  headers: string[]
): RawTransaction[] {
  const dateIdx = headers.findIndex((h) =>
    ["date", "data", "dt_transacao", "dt. transação"].includes(h)
  );
  const amountIdx = headers.findIndex((h) =>
    ["amount", "valor", "value", "vlr_transacao"].includes(h)
  );
  const descIdx = headers.findIndex((h) =>
    ["description", "descrição", "descricao", "historico", "título", "title", "memo"].includes(h)
  );

  if (dateIdx === -1 || amountIdx === -1) {
    throw new Error("Não foi possível identificar as colunas do CSV");
  }

  const transactions: RawTransaction[] = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const cols = line.split(delimiter).map((c) => c.trim().replace(/"/g, ""));
    const date = cols[dateIdx];
    const rawAmount = cols[amountIdx];
    const description = descIdx >= 0 ? cols[descIdx] : "Sem descrição";

    if (!date || !rawAmount) continue;

    const amount = parseFloat(
      rawAmount.replace(/[R$\s]/g, "").replace(/\./g, "").replace(",", ".")
    );
    if (isNaN(amount)) continue;

    transactions.push({
      date: parseDate(date),
      amount,
      description,
      type: amount >= 0 ? "income" : "expense",
      bank_slug: "generic",
      external_id: generateExternalId(date, amount, description),
    });
  }

  return transactions;
}

function parseDate(dateStr: string): string {
  // Handle DD/MM/YYYY
  if (dateStr.includes("/")) {
    const [day, month, year] = dateStr.split("/");
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  // Handle YYYY-MM-DD
  if (dateStr.includes("-") && dateStr.length === 10) {
    return dateStr;
  }
  return dateStr;
}
