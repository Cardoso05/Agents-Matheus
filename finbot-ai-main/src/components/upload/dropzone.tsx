"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Upload, FileText, Loader2, CheckCircle } from "lucide-react";
import { toast } from "sonner";
import { PreviewTable } from "./preview-table";

interface RawTransaction {
  date: string;
  amount: number;
  description: string;
  type: string;
  bank_slug: string;
  external_id: string;
}

interface UploadResult {
  transactions: RawTransaction[];
  duplicates_count: number;
  new_count: number;
  file_id: string;
  duplicate_ids: string[];
}

type UploadState = "idle" | "uploading" | "processing" | "preview" | "confirmed";

export function Dropzone() {
  const [state, setState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<UploadResult | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    setState("uploading");
    setProgress(0);

    for (const file of acceptedFiles) {
      const formData = new FormData();
      formData.append("file", file);

      setProgress(30);
      setState("processing");

      try {
        const res = await fetch("/api/upload", {
          method: "POST",
          body: formData,
        });

        setProgress(80);

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || "Erro ao processar arquivo");
        }

        const data = await res.json();
        setResult(data);
        setState("preview");
        setProgress(100);
        toast.success(`${data.new_count} novos lançamentos encontrados`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Erro ao processar arquivo");
        setState("idle");
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/pdf": [".pdf"],
      "application/x-ofx": [".ofx", ".qfx"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
    },
    multiple: true,
  });

  async function handleConfirm(selectedIds: string[]) {
    try {
      const selectedTransactions = result?.transactions.filter((t) =>
        selectedIds.includes(t.external_id)
      ) || [];

      const res = await fetch("/api/upload", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transactions: selectedTransactions,
        }),
      });

      if (!res.ok) throw new Error("Erro ao importar");

      toast.success("Lançamentos importados! Categorizando com IA...");

      // Chamar categorização automática
      try {
        const catRes = await fetch("/api/categorize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        if (catRes.ok) {
          const catData = await catRes.json();
          toast.success(`${catData.categorized} lançamentos categorizados pela IA!`);
        }
      } catch {
        toast.info("Lançamentos importados, mas a categorização falhou. Você pode categorizar manualmente.");
      }

      setState("confirmed");
    } catch {
      toast.error("Erro ao importar lançamentos");
    }
  }

  if (state === "preview" && result) {
    return (
      <PreviewTable
        transactions={result.transactions}
        duplicateIds={new Set(result.duplicate_ids || [])}
        onConfirm={handleConfirm}
        onCancel={() => {
          setState("idle");
          setResult(null);
        }}
      />
    );
  }

  if (state === "confirmed") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
          <CheckCircle className="h-12 w-12 text-green-500" />
          <p className="text-lg font-medium">Lançamentos importados!</p>
          <Button onClick={() => { setState("idle"); setResult(null); }}>
            Importar mais
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <div
          {...getRootProps()}
          className={`flex flex-col items-center justify-center py-16 px-6 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
            isDragActive ? "border-sky-500 bg-sky-50" : "border-slate-200 hover:border-slate-300"
          }`}
        >
          <input {...getInputProps()} />
          {state === "uploading" || state === "processing" ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-10 w-10 text-sky-500 animate-spin" />
              <p className="text-sm text-muted-foreground">
                {state === "uploading" ? "Enviando arquivo..." : "Processando extrato..."}
              </p>
              <div className="w-64 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-sky-500 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          ) : (
            <>
              <Upload className="h-10 w-10 text-slate-400 mb-3" />
              <p className="text-sm font-medium">
                {isDragActive ? "Solte o arquivo aqui" : "Arraste seus extratos ou clique para selecionar"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                PDF, CSV, OFX, QFX, JPG ou PNG
              </p>
              <div className="flex items-center gap-2 mt-4">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  Suportamos: Nubank, Itaú, Inter, Bradesco, C6, BB, Santander
                </span>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
