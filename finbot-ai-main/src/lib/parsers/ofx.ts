import { RawTransaction } from "./index";
import { generateExternalId } from "@/lib/utils/dedup";

export function parseOFX(file: Buffer): RawTransaction[] {
  const content = file.toString("utf-8");
  const transactions: RawTransaction[] = [];

  // Extract STMTTRN blocks
  const txRegex = /<STMTTRN>([\s\S]*?)<\/STMTTRN>/gi;
  let match;

  while ((match = txRegex.exec(content)) !== null) {
    const block = match[1];

    const dtPosted = extractTag(block, "DTPOSTED");
    const trnAmt = extractTag(block, "TRNAMT");
    const memo = extractTag(block, "MEMO") || extractTag(block, "NAME") || "";
    const fitId = extractTag(block, "FITID") || "";

    if (!dtPosted || !trnAmt) continue;

    const amount = parseFloat(trnAmt.replace(",", "."));
    if (isNaN(amount)) continue;

    const date = parseOFXDate(dtPosted);

    transactions.push({
      date,
      amount,
      description: memo.trim(),
      type: amount >= 0 ? "income" : "expense",
      bank_slug: detectBankFromOFX(content),
      external_id: fitId || generateExternalId(date, amount, memo),
    });
  }

  return transactions;
}

function extractTag(block: string, tag: string): string | null {
  // OFX format: <TAG>value or <TAG>value\n
  const regex = new RegExp(`<${tag}>([^<\\n]+)`, "i");
  const match = regex.exec(block);
  return match ? match[1].trim() : null;
}

function parseOFXDate(dateStr: string): string {
  // OFX date: YYYYMMDD or YYYYMMDDHHMMSS
  const year = dateStr.substring(0, 4);
  const month = dateStr.substring(4, 6);
  const day = dateStr.substring(6, 8);
  return `${year}-${month}-${day}`;
}

function detectBankFromOFX(content: string): string {
  const orgTag = extractTag(content, "ORG");
  if (!orgTag) return "generic";

  const org = orgTag.toLowerCase();
  if (org.includes("nubank") || org.includes("nu pagamentos")) return "nubank";
  if (org.includes("itau") || org.includes("itaú")) return "itau";
  if (org.includes("inter")) return "inter";
  if (org.includes("bradesco")) return "bradesco";
  if (org.includes("banco do brasil")) return "bb";
  if (org.includes("santander")) return "santander";
  if (org.includes("c6")) return "c6";
  return "generic";
}
