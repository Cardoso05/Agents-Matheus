import { describe, it, expect } from "vitest";
import { formatDate, formatMonthYear, getMonthRange } from "@/lib/utils/date";

describe("formatDate", () => {
  it("formats ISO string to DD/MM/YYYY", () => {
    expect(formatDate("2024-03-15")).toBe("15/03/2024");
  });

  it("formats Date object", () => {
    expect(formatDate(new Date(2024, 0, 1))).toBe("01/01/2024");
  });
});

describe("formatMonthYear", () => {
  it("formats to month name + year in pt-BR", () => {
    const result = formatMonthYear("2024-03-15");
    expect(result).toContain("2024");
    expect(result.toLowerCase()).toContain("março");
  });
});

describe("getMonthRange", () => {
  it("returns start and end of month", () => {
    const date = new Date(2024, 2, 15); // March 15
    const range = getMonthRange(date);
    expect(range.start.getDate()).toBe(1);
    expect(range.end.getDate()).toBe(31);
    expect(range.start.getMonth()).toBe(2);
  });
});
