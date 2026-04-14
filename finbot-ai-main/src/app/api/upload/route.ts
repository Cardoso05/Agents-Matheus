import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { parseFile } from "@/lib/parsers";

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const formData = await request.formData();
    const file = formData.get("file") as File;

    if (!file) {
      return NextResponse.json({ error: "Nenhum arquivo enviado" }, { status: 400 });
    }

    // Server-side validation: max 10MB
    const MAX_FILE_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { error: "Arquivo muito grande. Máximo permitido: 10MB." },
        { status: 400 }
      );
    }

    // Server-side validation: allowed extensions
    const allowedExtensions = [".csv", ".ofx", ".qfx", ".pdf"];
    const fileName = file.name.toLowerCase();
    const hasValidExtension = allowedExtensions.some((ext) => fileName.endsWith(ext));
    if (!hasValidExtension) {
      return NextResponse.json(
        { error: `Formato não suportado. Use: ${allowedExtensions.join(", ")}` },
        { status: 400 }
      );
    }

    const buffer = Buffer.from(await file.arrayBuffer());
    const transactions = await parseFile(buffer, file.name);

    // Fetch existing external_ids for dedup
    const externalIds = transactions.map((t) => t.external_id);
    const { data: existing } = await supabase
      .from("transactions")
      .select("external_id")
      .eq("user_id", user.id)
      .in("external_id", externalIds);

    const existingIds = new Set((existing || []).map((e) => e.external_id));
    const duplicateIds = externalIds.filter((id) => existingIds.has(id));
    const newTransactions = transactions.filter((t) => !existingIds.has(t.external_id));

    return NextResponse.json({
      transactions,
      duplicates_count: duplicateIds.length,
      new_count: newTransactions.length,
      file_id: file.name,
      duplicate_ids: duplicateIds,
    });
  } catch (error) {
    console.error("Upload error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao processar arquivo" },
      { status: 500 }
    );
  }
}

export async function PUT(request: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const body = await request.json();
    const { transactions, file_extension } = body as {
      transactions: {
        date: string;
        amount: number;
        description: string;
        type: string;
        bank_slug: string;
        external_id: string;
      }[];
      file_extension?: string;
    };

    if (!transactions || transactions.length === 0) {
      return NextResponse.json({ error: "Nenhuma transação para importar" }, { status: 400 });
    }

    // Determine correct source based on file extension
    const sourceMap: Record<string, "upload_csv" | "upload_ofx" | "upload_pdf"> = {
      csv: "upload_csv",
      ofx: "upload_ofx",
      qfx: "upload_ofx",
      pdf: "upload_pdf",
    };
    const source = sourceMap[file_extension?.toLowerCase() || "csv"] || "upload_csv";

    const rows = transactions.map((tx) => ({
      user_id: user.id,
      date: tx.date,
      amount: tx.amount,
      description: tx.description,
      type: tx.type as "income" | "expense" | "transfer",
      source,
      external_id: tx.external_id,
      metadata: { bank_slug: tx.bank_slug },
    }));

    const { data, error } = await supabase
      .from("transactions")
      .insert(rows)
      .select("id");

    if (error) {
      console.error("Supabase insert error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ imported: data?.length || 0 });
  } catch (error) {
    console.error("Import error:", error);
    return NextResponse.json({ error: "Erro ao importar" }, { status: 500 });
  }
}
