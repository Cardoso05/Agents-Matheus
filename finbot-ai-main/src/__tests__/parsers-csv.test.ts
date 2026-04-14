import { describe, it, expect } from "vitest";
import { parseCSV } from "@/lib/parsers/csv";

describe("parseCSV — Nubank format", () => {
  it("parses Nubank CSV with category and title columns", () => {
    const csv = `date,category,title,amount
2024-03-01,transporte,Uber,-25.50
2024-03-02,alimentação,iFood,-42.90
2024-03-03,,Salário,5000.00`;

    const txs = parseCSV(Buffer.from(csv));
    expect(txs).toHaveLength(3);
    expect(txs[0].description).toBe("Uber");
    expect(txs[0].amount).toBe(-25.5);
    expect(txs[0].type).toBe("expense");
    expect(txs[0].bank_slug).toBe("nubank");
    expect(txs[2].type).toBe("income");
  });
});

describe("parseCSV — generic format", () => {
  it("parses generic CSV with data/valor/descricao", () => {
    const csv = `data;valor;descricao
15/03/2024;-150,00;Conta de luz
20/03/2024;3.500,00;Salário`;

    const txs = parseCSV(Buffer.from(csv));
    expect(txs).toHaveLength(2);
    expect(txs[0].date).toBe("2024-03-15");
    expect(txs[0].amount).toBe(-150);
    expect(txs[1].amount).toBe(3500);
    expect(txs[1].type).toBe("income");
  });

  it("throws on empty CSV", () => {
    expect(() => parseCSV(Buffer.from("only header"))).toThrow();
  });

  it("throws when columns unrecognized", () => {
    const csv = `foo;bar;baz\n1;2;3`;
    expect(() => parseCSV(Buffer.from(csv))).toThrow("identificar as colunas");
  });
});
