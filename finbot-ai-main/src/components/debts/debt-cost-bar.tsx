"use client";

import { formatCurrency } from "@/lib/utils/currency";

interface DebtCostBarProps {
  originalAmount: number;
  currentBalance: number;
  interestRate: number;
  minimumPayment: number;
}

export function DebtCostBar({
  originalAmount,
  currentBalance,
  interestRate,
  minimumPayment,
}: DebtCostBarProps) {
  // Calculate total cost if only paying minimums
  let balance = currentBalance;
  let totalPaid = 0;
  const maxMonths = 360;

  for (let m = 0; m < maxMonths && balance > 0; m++) {
    const interest = balance * interestRate;
    balance += interest;
    const payment = Math.min(minimumPayment, balance);
    balance -= payment;
    totalPaid += payment;
  }

  const totalWithInterest = totalPaid;
  const interestTotal = Math.max(0, totalWithInterest - currentBalance);
  const interestPercent =
    currentBalance > 0 ? ((interestTotal / currentBalance) * 100) : 0;
  const principalWidth =
    totalWithInterest > 0
      ? (currentBalance / totalWithInterest) * 100
      : 100;
  const interestWidth = 100 - principalWidth;

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Você pegou{" "}
        <span className="font-semibold text-foreground">
          {formatCurrency(originalAmount)}
        </span>
        . Se pagar só o mínimo, vai pagar{" "}
        <span className="font-semibold text-foreground">
          {formatCurrency(totalWithInterest)}
        </span>
        .
      </p>
      <p className="text-sm text-red-600 font-medium">
        Ou seja, {formatCurrency(interestTotal)} só de juros — isso é{" "}
        {interestPercent.toFixed(0)}% a mais.
      </p>
      <div className="flex h-4 rounded-full overflow-hidden border">
        <div
          className="bg-sky-500 transition-all"
          style={{ width: `${principalWidth}%` }}
          title={`Principal: ${formatCurrency(currentBalance)}`}
        />
        <div
          className="bg-red-500 transition-all"
          style={{ width: `${interestWidth}%` }}
          title={`Juros: ${formatCurrency(interestTotal)}`}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-sky-500 inline-block" />
          Principal
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-red-500 inline-block" />
          Juros
        </span>
      </div>
    </div>
  );
}
