"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency } from "@/lib/utils/currency";
import { formatDate } from "@/lib/utils/date";

interface RawTransaction {
  date: string;
  amount: number;
  description: string;
  type: string;
  bank_slug: string;
  external_id: string;
}

interface PreviewTableProps {
  transactions: RawTransaction[];
  duplicateIds: Set<string>;
  onConfirm: (selectedIds: string[]) => void;
  onCancel: () => void;
}

export function PreviewTable({
  transactions,
  duplicateIds,
  onConfirm,
  onCancel,
}: PreviewTableProps) {
  const [selected, setSelected] = useState<Set<string>>(
    new Set(transactions.filter((t) => !duplicateIds.has(t.external_id)).map((t) => t.external_id))
  );

  function toggleSelect(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  const newCount = transactions.filter((t) => !duplicateIds.has(t.external_id)).length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">
          Preview — {newCount} novos, {duplicateIds.size} duplicados
        </CardTitle>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancelar
          </Button>
          <Button onClick={() => onConfirm(Array.from(selected))} disabled={selected.size === 0}>
            Importar {selected.size} lançamentos
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Data</TableHead>
                <TableHead>Descrição</TableHead>
                <TableHead className="text-right">Valor</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((tx) => {
                const isDuplicate = duplicateIds.has(tx.external_id);
                return (
                  <TableRow
                    key={tx.external_id}
                    className={isDuplicate ? "opacity-50" : ""}
                  >
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selected.has(tx.external_id)}
                        onChange={() => toggleSelect(tx.external_id)}
                        disabled={isDuplicate}
                        className="rounded"
                      />
                    </TableCell>
                    <TableCell className="text-sm">{formatDate(tx.date)}</TableCell>
                    <TableCell className="text-sm max-w-xs truncate">
                      {tx.description}
                    </TableCell>
                    <TableCell
                      className={`text-sm text-right font-medium ${
                        tx.type === "income" ? "text-green-600" : "text-red-600"
                      }`}
                    >
                      {formatCurrency(Math.abs(tx.amount))}
                    </TableCell>
                    <TableCell>
                      <Badge variant={tx.type === "income" ? "default" : "destructive"}>
                        {tx.type === "income" ? "Receita" : "Despesa"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {isDuplicate ? (
                        <Badge variant="secondary">Já importado</Badge>
                      ) : (
                        <Badge variant="outline" className="text-green-600 border-green-600">
                          Novo
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
