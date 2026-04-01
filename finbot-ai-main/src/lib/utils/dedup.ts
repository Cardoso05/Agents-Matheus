import { createHash } from "crypto";

export function generateExternalId(
  date: string,
  amount: number,
  description: string
): string {
  const raw = `${date}|${amount}|${description.trim().toLowerCase()}`;
  return createHash("sha256").update(raw).digest("hex").slice(0, 16);
}

export function findDuplicates(
  newIds: string[],
  existingIds: string[]
): Set<string> {
  const existing = new Set(existingIds);
  return new Set(newIds.filter((id) => existing.has(id)));
}
