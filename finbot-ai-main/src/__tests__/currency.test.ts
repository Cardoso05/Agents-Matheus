import { describe, it, expect } from "vitest";
import { formatCurrency, parseCurrencyBRL } from "@/lib/utils/currency";

describe("formatCurrency", () => {
  it("formats positive values in BRL", () => {
    const result = formatCurrency(1234.56);
    expect(result).toContain("1.234,56");
  });

  it("formats zero", () => {
    const result = formatCurrency(0);
    expect(result).toContain("0,00");
  });

  it("formats negative values", () => {
    const result = formatCurrency(-500);
    expect(result).toContain("500,00");
  });
});

describe("parseCurrencyBRL", () => {
  it("parses R$ 1.234,56", () => {
    expect(parseCurrencyBRL("R$ 1.234,56")).toBe(1234.56);
  });

  it("parses simple value", () => {
    expect(parseCurrencyBRL("100,50")).toBe(100.50);
  });

  it("parses value without decimals", () => {
    expect(parseCurrencyBRL("R$ 500")).toBe(500);
  });
});
