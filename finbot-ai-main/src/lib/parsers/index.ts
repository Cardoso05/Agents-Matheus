import { parseCSV } from "./csv";
import { parseOFX } from "./ofx";
import { parsePDF } from "./pdf";

export interface RawTransaction {
  date: string;
  amount: number;
  description: string;
  type: "income" | "expense" | "transfer";
  bank_slug: string;
  external_id: string;
}

export async function parseFile(
  file: Buffer,
  filename: string
): Promise<RawTransaction[]> {
  const ext = filename.split(".").pop()?.toLowerCase();

  if (ext === "csv") return parseCSV(file);
  if (ext === "ofx" || ext === "qfx") return parseOFX(file);
  if (ext === "pdf") return parsePDF(file);

  throw new Error(`Formato não suportado: ${ext}`);
}
