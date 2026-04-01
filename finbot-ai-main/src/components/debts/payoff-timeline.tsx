"use client";

import { formatCurrency } from "@/lib/utils/currency";

interface TimelineMilestone {
  month: number;
  monthLabel: string;
  debtName: string;
  isCurrent: boolean;
  isFinal: boolean;
  freedPayment?: number;
  nextDebtName?: string;
}

interface PayoffTimelineProps {
  milestones: TimelineMilestone[];
}

export function PayoffTimeline({ milestones }: PayoffTimelineProps) {
  if (milestones.length === 0) return null;

  return (
    <div className="relative pl-8">
      {/* Vertical line */}
      <div className="absolute left-3 top-2 bottom-2 w-0.5 bg-slate-200" />

      <div className="space-y-6">
        {milestones.map((m, i) => (
          <div key={i} className="relative">
            {/* Dot */}
            <div
              className={`absolute -left-5 top-1 h-4 w-4 rounded-full border-2 ${
                m.isCurrent
                  ? "border-sky-500 bg-sky-500 animate-pulse"
                  : m.isFinal
                  ? "border-amber-500 bg-amber-500"
                  : "border-sky-300 bg-white"
              }`}
            />

            <div
              className={`rounded-lg p-3 ${
                m.isCurrent
                  ? "bg-sky-50 border border-sky-200"
                  : m.isFinal
                  ? "bg-amber-50 border border-amber-200"
                  : "bg-slate-50 border border-slate-100"
              }`}
            >
              <p className="text-xs text-muted-foreground font-medium">
                {m.monthLabel}
                {m.isCurrent && (
                  <span className="ml-2 text-sky-600 font-semibold">
                    ← Você está aqui
                  </span>
                )}
              </p>

              {m.isFinal ? (
                <p className="font-bold text-amber-700 mt-1">
                  LIVRE DE DIVIDAS! {"\u{1F3C6}"}
                </p>
              ) : (
                <>
                  <p className="font-semibold mt-1">
                    {m.debtName} quitado! {"\u{1F389}"}
                  </p>
                  {m.freedPayment && m.nextDebtName && (
                    <p className="text-sm text-muted-foreground mt-0.5">
                      A parcela de {formatCurrency(m.freedPayment)} vai para{" "}
                      <span className="font-medium text-foreground">
                        {m.nextDebtName}
                      </span>
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
