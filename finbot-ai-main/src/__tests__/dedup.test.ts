import { describe, it, expect } from "vitest";
import { generateExternalId, findDuplicates } from "@/lib/utils/dedup";

describe("generateExternalId", () => {
  it("generates a 16-char hex string", () => {
    const id = generateExternalId("2024-01-15", -50.0, "Supermercado");
    expect(id).toHaveLength(16);
    expect(id).toMatch(/^[a-f0-9]{16}$/);
  });

  it("is deterministic", () => {
    const a = generateExternalId("2024-01-15", -50.0, "Test");
    const b = generateExternalId("2024-01-15", -50.0, "Test");
    expect(a).toBe(b);
  });

  it("differs for different inputs", () => {
    const a = generateExternalId("2024-01-15", -50.0, "A");
    const b = generateExternalId("2024-01-15", -50.0, "B");
    expect(a).not.toBe(b);
  });
});

describe("findDuplicates", () => {
  it("finds overlapping ids", () => {
    const dupes = findDuplicates(["a", "b", "c"], ["b", "c", "d"]);
    expect(dupes).toEqual(new Set(["b", "c"]));
  });

  it("returns empty set when no duplicates", () => {
    const dupes = findDuplicates(["a"], ["b"]);
    expect(dupes.size).toBe(0);
  });
});
