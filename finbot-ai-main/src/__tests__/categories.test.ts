import { describe, it, expect } from "vitest";
import { CATEGORY_GROUPS } from "@/lib/constants/categories";

describe("CATEGORY_GROUPS", () => {
  it("has all expected groups", () => {
    const keys = Object.keys(CATEGORY_GROUPS);
    expect(keys).toContain("moradia");
    expect(keys).toContain("transporte");
    expect(keys).toContain("alimentação");
    expect(keys).toContain("renda");
    expect(keys).toContain("financeiro");
    expect(keys).toContain("outros");
  });

  it("each group has label, color and type", () => {
    for (const [, group] of Object.entries(CATEGORY_GROUPS)) {
      expect(group).toHaveProperty("label");
      expect(group).toHaveProperty("color");
      expect(group).toHaveProperty("type");
      expect(group.color).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it("has exactly one income group (renda)", () => {
    const incomeGroups = Object.entries(CATEGORY_GROUPS).filter(
      ([, g]) => g.type === "income"
    );
    expect(incomeGroups).toHaveLength(1);
    expect(incomeGroups[0][0]).toBe("renda");
  });

  it("has at least one saving group", () => {
    const savingGroups = Object.entries(CATEGORY_GROUPS).filter(
      ([, g]) => g.type === "saving"
    );
    expect(savingGroups.length).toBeGreaterThanOrEqual(1);
  });
});
