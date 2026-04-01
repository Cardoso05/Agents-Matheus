"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency } from "@/lib/utils/currency";
import { createClient } from "@/lib/supabase/client";
import { toast } from "sonner";

interface PaymentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  debt: {
    id: string;
    name: string;
    current_balance: number;
    interest_rate: number;
  } | null;
  suggestedAmount: number;
  onPaymentSaved: () => void;
}

export function PaymentDialog({
  open,
  onOpenChange,
  debt,
  suggestedAmount,
  onPaymentSaved,
}: PaymentDialogProps) {
  const [amount, setAmount] = useState(suggestedAmount);
  const [date, setDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [isExtra, setIsExtra] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const supabase = createClient();

  // Reset state when dialog opens with new debt
  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen && debt) {
      setAmount(suggestedAmount);
      setDate(new Date().toISOString().split("T")[0]);
      setIsExtra(false);
      setNotes("");
      setShowConfetti(false);
    }
    onOpenChange(newOpen);
  };

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!debt) return;
    setSaving(true);

    try {
      // Insert payment
      const { error: paymentError } = await supabase
        .from("debt_payments")
        .insert({
          debt_id: debt.id,
          date,
          amount,
          is_extra: isExtra,
          notes: notes || null,
        });

      if (paymentError) throw paymentError;

      // Update debt balance
      const oldBalance = Number(debt.current_balance);
      const newBalance = Math.max(0, oldBalance - amount);

      const updateData: Record<string, unknown> = {
        current_balance: newBalance,
      };
      if (newBalance <= 0) {
        updateData.status = "paid_off";
      }

      const { error: updateError } = await supabase
        .from("debts")
        .update(updateData)
        .eq("id", debt.id);

      if (updateError) throw updateError;

      // Celebration!
      if (newBalance <= 0) {
        setShowConfetti(true);
        toast.success(
          `${debt.name} QUITADA! Parabéns! \u{1F389}\u{1F38A}`,
          { duration: 5000 }
        );
        setTimeout(() => {
          setShowConfetti(false);
          onOpenChange(false);
          onPaymentSaved();
        }, 3000);
      } else {
        let message = `Pagamento de ${formatCurrency(amount)} registrado!\nSaldo: ${formatCurrency(newBalance)} (era ${formatCurrency(oldBalance)})`;

        if (isExtra) {
          const estimatedSavings = amount * debt.interest_rate * 3;
          message += `\nVocê economizou ~${formatCurrency(estimatedSavings)} em juros com esse extra! \u{1F4AA}`;
        }

        toast.success(message, { duration: 4000 });
        onOpenChange(false);
        onPaymentSaved();
      }
    } catch {
      toast.error("Erro ao registrar pagamento. Tente novamente.");
    } finally {
      setSaving(false);
    }
  }

  if (!debt) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="relative overflow-hidden">
        {showConfetti && (
          <div className="absolute inset-0 pointer-events-none z-50">
            {Array.from({ length: 40 }).map((_, i) => (
              <div
                key={i}
                className="absolute animate-confetti"
                style={{
                  left: `${Math.random() * 100}%`,
                  animationDelay: `${Math.random() * 1}s`,
                  animationDuration: `${1.5 + Math.random() * 1.5}s`,
                  backgroundColor: [
                    "#22c55e",
                    "#3b82f6",
                    "#f59e0b",
                    "#ef4444",
                    "#8b5cf6",
                    "#06b6d4",
                  ][i % 6],
                  width: `${6 + Math.random() * 6}px`,
                  height: `${6 + Math.random() * 6}px`,
                  borderRadius: Math.random() > 0.5 ? "50%" : "0",
                }}
              />
            ))}
          </div>
        )}

        <DialogHeader>
          <DialogTitle>Registrar Pagamento</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="space-y-2">
            <Label>Dívida</Label>
            <Input value={debt.name} readOnly className="bg-muted" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pay-amount">Valor do Pagamento</Label>
            <Input
              id="pay-amount"
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="pay-date">Data</Label>
            <Input
              id="pay-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              role="switch"
              aria-checked={isExtra}
              onClick={() => setIsExtra(!isExtra)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                isExtra ? "bg-sky-500" : "bg-slate-200"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${
                  isExtra ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
            <Label className="cursor-pointer" onClick={() => setIsExtra(!isExtra)}>
              Pagamento extra?
            </Label>
          </div>

          <div className="space-y-2">
            <Label htmlFor="pay-notes">Observações (opcional)</Label>
            <Textarea
              id="pay-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex: 13º salário, venda de item..."
              rows={2}
            />
          </div>

          <Button type="submit" className="w-full" disabled={saving}>
            {saving ? "Salvando..." : "Confirmar Pagamento"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
