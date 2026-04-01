import { createHash } from "crypto";

/**
 * Generate a deterministic external ID for deduplication.
 * The optional `index` parameter differentiates identical transactions
 * within the same file (e.g., two R$5.00 purchases at Starbucks on the same day).
 */
export function generateExternalId(
  date: string,
  amount: number,
  description: string,
  index?: number
): string {
  const parts = [date, String(amount), description.trim().toLowerCase()];
  if (index !== undefined) {
    parts.push(String(index));
  }
  const raw = parts.join("|");
  return createHash("sha256").update(raw).digest("hex").slice(0, 16);
}

export function findDuplicates(
  newIds: string[],
  existingIds: string[]
): Set<string> {
  const existing = new Set(existingIds);
  return new Set(newIds.filter((id) => existing.has(id)));
}
