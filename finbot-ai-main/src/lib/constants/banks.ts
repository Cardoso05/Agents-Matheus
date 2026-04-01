export const SUPPORTED_BANKS = [
  { slug: "nubank", name: "Nubank", color: "#820AD1", formats: ["csv", "ofx", "pdf"] },
  { slug: "itau", name: "Itaú", color: "#003399", formats: ["csv", "ofx", "pdf"] },
  { slug: "inter", name: "Inter", color: "#FF7A00", formats: ["csv", "ofx", "pdf"] },
  { slug: "bradesco", name: "Bradesco", color: "#CC092F", formats: ["csv", "ofx", "pdf"] },
  { slug: "c6", name: "C6 Bank", color: "#2A2A2A", formats: ["csv", "ofx"] },
  { slug: "bb", name: "Banco do Brasil", color: "#FFEF00", formats: ["csv", "ofx", "pdf"] },
  { slug: "santander", name: "Santander", color: "#EC0000", formats: ["csv", "ofx", "pdf"] },
] as const;

export type BankSlug = (typeof SUPPORTED_BANKS)[number]["slug"];
