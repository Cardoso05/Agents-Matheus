import { describe, it, expect } from "vitest";
import { parseOFX } from "@/lib/parsers/ofx";

const sampleOFX = `
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20240315
<TRNAMT>-89.90
<FITID>2024031501
<MEMO>SUPERMERCADO EXTRA
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20240320
<TRNAMT>5000.00
<FITID>2024032001
<MEMO>SALARIO
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>`;

describe("parseOFX", () => {
  it("extracts transactions from OFX blocks", () => {
    const txs = parseOFX(Buffer.from(sampleOFX));
    expect(txs).toHaveLength(2);
  });

  it("parses date correctly", () => {
    const txs = parseOFX(Buffer.from(sampleOFX));
    expect(txs[0].date).toBe("2024-03-15");
  });

  it("parses amounts and types", () => {
    const txs = parseOFX(Buffer.from(sampleOFX));
    expect(txs[0].amount).toBe(-89.9);
    expect(txs[0].type).toBe("expense");
    expect(txs[1].amount).toBe(5000);
    expect(txs[1].type).toBe("income");
  });

  it("uses FITID as external_id", () => {
    const txs = parseOFX(Buffer.from(sampleOFX));
    expect(txs[0].external_id).toBe("2024031501");
  });

  it("extracts memo/description", () => {
    const txs = parseOFX(Buffer.from(sampleOFX));
    expect(txs[0].description).toBe("SUPERMERCADO EXTRA");
  });

  it("returns empty array for invalid OFX", () => {
    const txs = parseOFX(Buffer.from("<OFX>no transactions</OFX>"));
    expect(txs).toHaveLength(0);
  });
});
