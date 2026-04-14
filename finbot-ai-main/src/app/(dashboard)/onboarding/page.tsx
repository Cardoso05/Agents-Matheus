"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { formatCurrency } from "@/lib/utils/currency";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Dropzone } from "@/components/upload/dropzone";
import {
  AlertTriangle,
  BarChart3,
  TrendingUp,
  ArrowLeft,
  Plus,
  Trash2,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

type Situation = "endividado" | "organizar" | "investir";

interface DebtEntry {
  id: string;
  type: string;
  customName: string;
  balance: number;
  interestRate: number;
  minPayment: number;
}

const DEBT_TYPE_OPTIONS = [
  "Cartao de credito",
  "Emprestimo pessoal",
  "Financiamento",
  "Cheque especial",
  "Carne de loja",
  "Outro",
] as const;

const TOTAL_STEPS = 5;

function emptyDebt(): DebtEntry {
  return {
    id: crypto.randomUUID(),
    type: "",
    customName: "",
    balance: 0,
    interestRate: 0,
    minPayment: 0,
  };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function debtDisplayName(d: DebtEntry): string {
  if (d.type === "Outro" && d.customName) return d.customName;
  return d.type || "Divida";
}

/** Calculate months to payoff and total interest with minimum payments. */
function calcMinPaymentSchedule(balance: number, monthlyRate: number, minPayment: number) {
  if (balance <= 0) return { months: 0, totalInterest: 0 };
  const payment = minPayment > 0 ? minPayment : balance * 0.03;
  if (payment <= 0) return { months: 0, totalInterest: 0 };

  let remaining = balance;
  let months = 0;
  let totalInterest = 0;
  const maxMonths = 600; // cap at 50 years

  while (remaining > 0.01 && months < maxMonths) {
    const interest = remaining * (monthlyRate / 100);
    totalInterest += interest;
    remaining += interest;
    const actualPayment = Math.min(payment, remaining);
    remaining -= actualPayment;
    months++;

    // If payment doesn't cover interest, debt grows forever
    if (payment <= interest && months > 1) {
      return { months: Infinity, totalInterest: Infinity };
    }
  }

  return { months, totalInterest };
}

/** Avalanche method: pay debts ordered by highest interest rate first. */
function calcAvalancheSchedule(
  debts: DebtEntry[],
  monthlyAvailable: number
) {
  if (debts.length === 0 || monthlyAvailable <= 0) {
    return { months: 0, totalInterest: 0 };
  }

  // Sort by interest rate descending (avalanche)
  const sorted = debts
    .filter((d) => d.balance > 0)
    .map((d) => ({
      balance: d.balance,
      rate: d.interestRate / 100,
      minPayment: d.minPayment > 0 ? d.minPayment : d.balance * 0.03,
    }));

  if (sorted.length === 0) return { months: 0, totalInterest: 0 };

  sorted.sort((a, b) => b.rate - a.rate);

  let months = 0;
  let totalInterest = 0;
  const maxMonths = 600;

  while (sorted.some((d) => d.balance > 0.01) && months < maxMonths) {
    months++;
    let available = monthlyAvailable;

    // Accrue interest
    for (const d of sorted) {
      if (d.balance <= 0) continue;
      const interest = d.balance * d.rate;
      totalInterest += interest;
      d.balance += interest;
    }

    // Pay minimums first
    for (const d of sorted) {
      if (d.balance <= 0) continue;
      const payment = Math.min(d.minPayment, d.balance, available);
      d.balance -= payment;
      available -= payment;
    }

    // Extra payments to highest interest first
    for (const d of sorted) {
      if (available <= 0) break;
      if (d.balance <= 0) continue;
      const extra = Math.min(d.balance, available);
      d.balance -= extra;
      available -= extra;
    }
  }

  return { months, totalInterest };
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  // Step 1
  const [situation, setSituation] = useState<Situation | null>(null);

  // Step 2
  const [monthlyIncome, setMonthlyIncome] = useState("");
  const [variableIncome, setVariableIncome] = useState("");

  // Step 3
  const [debts, setDebts] = useState<DebtEntry[]>([emptyDebt()]);

  // Step 4 — tracked for skip
  const [importSkipped, setImportSkipped] = useState(false);

  // Derived values
  const incomeFixed = parseFloat(monthlyIncome) || 0;
  const incomeVariable = parseFloat(variableIncome) || 0;
  const totalIncome = incomeFixed + incomeVariable;

  const totalDebt = useMemo(
    () => debts.reduce((sum, d) => sum + (d.balance || 0), 0),
    [debts]
  );

  const rescueMode = situation === "endividado";

  // ─── Step navigation ──────────────────────────────────────────────────────

  function goNext() {
    setStep((s) => Math.min(s + 1, TOTAL_STEPS));
  }

  function goBack() {
    setStep((s) => Math.max(s - 1, 1));
  }

  // ─── Debt management ──────────────────────────────────────────────────────

  function addDebt() {
    setDebts((prev) => [...prev, emptyDebt()]);
  }

  function removeDebt(id: string) {
    setDebts((prev) => (prev.length === 1 ? prev : prev.filter((d) => d.id !== id)));
  }

  function updateDebt(id: string, field: keyof DebtEntry, value: string | number) {
    setDebts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, [field]: value } : d))
    );
  }

  // ─── Save & finish ────────────────────────────────────────────────────────

  async function handleFinish() {
    setSaving(true);
    try {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      // Update profile
      const { error: profileError } = await supabase
        .from("profiles")
        .update({
          onboarding_completed: true,
          is_rescue_mode: rescueMode,
          monthly_income: incomeFixed,
          variable_income: incomeVariable,
          rescue_started_at: rescueMode ? new Date().toISOString() : null,
        })
        .eq("id", user.id);

      if (profileError) throw profileError;

      // Insert debts
      const validDebts = debts.filter((d) => d.balance > 0 && d.type);
      if (validDebts.length > 0) {
        const rows = validDebts.map((d, i) => ({
          user_id: user.id,
          name: debtDisplayName(d),
          original_amount: d.balance,
          current_balance: d.balance,
          interest_rate: d.interestRate / 100, // store as decimal
          minimum_payment: d.minPayment || d.balance * 0.03,
          priority: i,
          status: "active" as const,
        }));

        const { error: debtsError } = await supabase.from("debts").insert(rows);
        if (debtsError) throw debtsError;
      }

      router.push("/dashboard");
    } catch (err) {
      console.error("Onboarding save error:", err);
      setSaving(false);
    }
  }

  // ─── Diagnosis calculations (Step 5) ──────────────────────────────────────

  const diagnosis = useMemo(() => {
    const validDebts = debts.filter((d) => d.balance > 0);
    if (validDebts.length === 0) {
      return {
        currentMonths: 0,
        currentInterest: 0,
        optimizedMonths: 0,
        optimizedInterest: 0,
        savedInterest: 0,
        currentMinPayments: 0,
      };
    }

    // Sum of current minimum payments
    let currentMonths = 0;
    let currentInterest = 0;
    let currentMinPayments = 0;

    for (const d of validDebts) {
      const minPay = d.minPayment > 0 ? d.minPayment : d.balance * 0.03;
      currentMinPayments += minPay;
      const result = calcMinPaymentSchedule(d.balance, d.interestRate, minPay);
      if (result.months > currentMonths) currentMonths = result.months;
      currentInterest += result.totalInterest;
    }

    // Avalanche with extra available money
    // Estimate 80% of income goes to living expenses
    const estimatedExpenses = totalIncome * 0.8;
    const available = Math.max(totalIncome - estimatedExpenses, currentMinPayments);
    const avalanche = calcAvalancheSchedule(validDebts, available);

    return {
      currentMonths,
      currentInterest,
      optimizedMonths: avalanche.months,
      optimizedInterest: avalanche.totalInterest,
      savedInterest: Math.max(currentInterest - avalanche.totalInterest, 0),
      currentMinPayments,
    };
  }, [debts, totalIncome]);

  // ─── Step indicator ────────────────────────────────────────────────────────

  function StepIndicator() {
    return (
      <div className="w-full max-w-md mx-auto mb-8">
        <Progress value={(step / TOTAL_STEPS) * 100} className="h-2" />
        <p className="text-center text-sm text-slate-500 mt-2">
          Passo {step} de {TOTAL_STEPS}
        </p>
      </div>
    );
  }

  // ─── Render steps ──────────────────────────────────────────────────────────

  function renderStep1() {
    const options: {
      value: Situation;
      label: string;
      description: string;
      icon: typeof AlertTriangle;
      color: string;
      bgColor: string;
    }[] = [
      {
        value: "endividado",
        label: "Estou endividado e quero sair",
        description: "Vamos montar um plano de resgate para voce quitar suas dividas",
        icon: AlertTriangle,
        color: "text-red-500",
        bgColor: "bg-red-50 border-red-200 hover:border-red-400",
      },
      {
        value: "organizar",
        label: "Quero organizar meu dinheiro",
        description: "Vamos te ajudar a ter controle total das suas financas",
        icon: BarChart3,
        color: "text-blue-500",
        bgColor: "bg-blue-50 border-blue-200 hover:border-blue-400",
      },
      {
        value: "investir",
        label: "Quero comecar a guardar/investir",
        description: "Vamos criar um plano para voce comecar a construir patrimonio",
        icon: TrendingUp,
        color: "text-green-500",
        bgColor: "bg-green-50 border-green-200 hover:border-green-400",
      },
    ];

    return (
      <div className="text-center">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          Qual sua situacao?
        </h1>
        <p className="text-slate-500 mb-8">
          Escolha a opcao que melhor descreve seu momento financeiro
        </p>
        <div className="grid gap-4 max-w-lg mx-auto">
          {options.map((opt) => {
            const Icon = opt.icon;
            return (
              <Card
                key={opt.value}
                className={`cursor-pointer border-2 transition-all ${opt.bgColor} ${
                  situation === opt.value ? "ring-2 ring-sky-500" : ""
                }`}
                onClick={() => {
                  setSituation(opt.value);
                  goNext();
                }}
              >
                <CardContent className="flex items-center gap-4 p-6">
                  <div className={`${opt.color}`}>
                    <Icon className="h-8 w-8" />
                  </div>
                  <div className="text-left">
                    <p className="font-semibold text-slate-900">{opt.label}</p>
                    <p className="text-sm text-slate-600">{opt.description}</p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    );
  }

  function renderStep2() {
    return (
      <div className="max-w-md mx-auto">
        <h1 className="text-3xl font-bold text-slate-900 mb-2 text-center">
          Quanto voce ganha?
        </h1>
        <p className="text-slate-500 mb-8 text-center">
          Informe sua renda mensal para calcularmos seu plano
        </p>

        <div className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="monthly-income">
              Renda fixa mensal (salario/pro-labore) *
            </Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">
                R$
              </span>
              <Input
                id="monthly-income"
                type="number"
                min="0"
                step="0.01"
                placeholder="0,00"
                className="pl-10"
                value={monthlyIncome}
                onChange={(e) => setMonthlyIncome(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="variable-income">
              Renda variavel media (projetos, freelance)
            </Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">
                R$
              </span>
              <Input
                id="variable-income"
                type="number"
                min="0"
                step="0.01"
                placeholder="0,00"
                className="pl-10"
                value={variableIncome}
                onChange={(e) => setVariableIncome(e.target.value)}
              />
            </div>
          </div>

          <div className="rounded-lg bg-slate-50 p-4 text-center">
            <p className="text-sm text-slate-500">Renda mensal estimada</p>
            <p className="text-2xl font-bold text-slate-900">
              {formatCurrency(totalIncome)}
            </p>
          </div>

          <Button
            className="w-full bg-sky-500 hover:bg-sky-600"
            size="lg"
            disabled={incomeFixed <= 0}
            onClick={goNext}
          >
            Continuar
          </Button>
        </div>
      </div>
    );
  }

  function renderStep3() {
    return (
      <div className="max-w-lg mx-auto">
        <h1 className="text-3xl font-bold text-slate-900 mb-2 text-center">
          Quais sao suas dividas?
        </h1>
        <p className="text-slate-500 mb-4 text-center">
          Liste todas as suas dividas para montarmos o melhor plano
        </p>

        {/* Running total */}
        <div className="rounded-lg bg-red-50 p-4 text-center mb-6">
          <p className="text-sm text-red-600">Divida total</p>
          <p className="text-2xl font-bold text-red-600">
            {formatCurrency(totalDebt)}
          </p>
        </div>

        <div className="space-y-6">
          {debts.map((debt, index) => (
            <Card key={debt.id} className="relative">
              <CardContent className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-slate-700 text-sm">
                    Divida {index + 1}
                  </p>
                  {debts.length > 1 && (
                    <button
                      onClick={() => removeDebt(debt.id)}
                      className="text-slate-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Tipo da divida</Label>
                  <Select
                    value={debt.type}
                    onValueChange={(val) => updateDebt(debt.id, "type", val)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Selecione o tipo" />
                    </SelectTrigger>
                    <SelectContent>
                      {DEBT_TYPE_OPTIONS.map((opt) => (
                        <SelectItem key={opt} value={opt}>
                          {opt}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {debt.type === "Outro" && (
                  <div className="space-y-2">
                    <Label>Nome da divida</Label>
                    <Input
                      placeholder="Ex: Divida com familiar"
                      value={debt.customName}
                      onChange={(e) =>
                        updateDebt(debt.id, "customName", e.target.value)
                      }
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label>Quanto deve hoje?</Label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">
                      R$
                    </span>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="0,00"
                      className="pl-10"
                      value={debt.balance || ""}
                      onChange={(e) =>
                        updateDebt(debt.id, "balance", parseFloat(e.target.value) || 0)
                      }
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Juros mensais (%)</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0"
                    value={debt.interestRate || ""}
                    onChange={(e) =>
                      updateDebt(
                        debt.id,
                        "interestRate",
                        parseFloat(e.target.value) || 0
                      )
                    }
                  />
                  <p className="text-xs text-slate-400">
                    Nao sabe? Cartao: ~14%, Emprestimo: ~2%, Cheque especial: ~8%
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>Parcela mensal (se houver)</Label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">
                      R$
                    </span>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="0,00"
                      className="pl-10"
                      value={debt.minPayment || ""}
                      onChange={(e) =>
                        updateDebt(
                          debt.id,
                          "minPayment",
                          parseFloat(e.target.value) || 0
                        )
                      }
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          <Button
            variant="outline"
            className="w-full"
            onClick={addDebt}
          >
            <Plus className="h-4 w-4 mr-2" />
            Adicionar outra divida
          </Button>

          <div className="flex flex-col gap-2">
            <Button
              className="w-full bg-sky-500 hover:bg-sky-600"
              size="lg"
              onClick={goNext}
            >
              Continuar
            </Button>
            <button
              className="text-sm text-slate-400 hover:text-slate-600 underline"
              onClick={() => {
                setDebts([emptyDebt()]);
                goNext();
              }}
            >
              Nao tenho dividas
            </button>
          </div>
        </div>
      </div>
    );
  }

  function renderStep4() {
    if (importSkipped) {
      // Auto-advance was triggered, go to step 5
      return null;
    }

    return (
      <div className="max-w-md mx-auto">
        <h1 className="text-3xl font-bold text-slate-900 mb-2 text-center">
          Importe seu extrato
        </h1>
        <p className="text-slate-500 mb-8 text-center">
          Jogue aqui o extrato do seu banco (CSV ou OFX)
        </p>

        <Dropzone />

        <div className="mt-6 text-center">
          <Button
            variant="outline"
            className="w-full"
            onClick={() => {
              setImportSkipped(true);
              goNext();
            }}
          >
            Pular e preencher depois
          </Button>
        </div>
      </div>
    );
  }

  function renderStep5() {
    const validDebts = debts.filter((d) => d.balance > 0);
    const hasDebts = validDebts.length > 0;

    const currentYears =
      diagnosis.currentMonths === Infinity
        ? "infinitos"
        : diagnosis.currentMonths < 12
          ? `${diagnosis.currentMonths} meses`
          : `${(diagnosis.currentMonths / 12).toFixed(1)} anos`;

    const optimizedMonthsDisplay =
      diagnosis.optimizedMonths === Infinity
        ? "muito tempo"
        : `${diagnosis.optimizedMonths} meses`;

    return (
      <div className="max-w-lg mx-auto text-center">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          Seu diagnostico
        </h1>
        <p className="text-slate-500 mb-8">
          Aqui esta uma visao geral da sua situacao financeira
        </p>

        <div className="grid gap-4 mb-8">
          {/* Income */}
          <Card className="border-green-200 bg-green-50">
            <CardContent className="p-6 text-center">
              <p className="text-4xl mb-1">&#128176;</p>
              <p className="text-sm text-green-700 mb-1">Renda estimada</p>
              <p className="text-3xl font-bold text-green-700">
                {formatCurrency(totalIncome)}
              </p>
            </CardContent>
          </Card>

          {/* Debt */}
          {hasDebts && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="p-6 text-center">
                <p className="text-4xl mb-1">&#128308;</p>
                <p className="text-sm text-red-700 mb-1">Divida total</p>
                <p className="text-3xl font-bold text-red-700">
                  {formatCurrency(totalDebt)}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Timeline */}
          {hasDebts && (
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="p-6 text-center">
                <p className="text-4xl mb-1">&#9200;</p>
                <p className="text-sm text-amber-700 mb-1">No ritmo atual</p>
                <p className="text-lg font-bold text-amber-700">
                  Voce leva{" "}
                  <span className="text-2xl">{currentYears}</span> para quitar
                  tudo
                </p>
                {diagnosis.currentInterest !== Infinity && (
                  <p className="text-sm text-amber-600 mt-1">
                    Pagando{" "}
                    <span className="font-semibold">
                      {formatCurrency(diagnosis.currentInterest)}
                    </span>{" "}
                    em juros
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Optimized plan */}
        {hasDebts && diagnosis.savedInterest > 0 && (
          <Card className="border-sky-200 bg-sky-50 mb-8">
            <CardContent className="p-6 text-center">
              <p className="text-lg font-semibold text-sky-800 mb-2">
                Com o plano FinBot, voce pode quitar em{" "}
                <span className="text-sky-600">{optimizedMonthsDisplay}</span>{" "}
                e economizar{" "}
                <span className="text-sky-600">
                  {formatCurrency(diagnosis.savedInterest)}
                </span>{" "}
                em juros
              </p>
            </CardContent>
          </Card>
        )}

        {!hasDebts && (
          <Card className="border-sky-200 bg-sky-50 mb-8">
            <CardContent className="p-6 text-center">
              <p className="text-lg font-semibold text-sky-800">
                Otimo! Voce nao tem dividas. Vamos organizar suas financas e
                fazer seu dinheiro render mais.
              </p>
            </CardContent>
          </Card>
        )}

        <Button
          className="w-full bg-sky-500 hover:bg-sky-600"
          size="lg"
          disabled={saving}
          onClick={handleFinish}
        >
          {saving
            ? "Salvando..."
            : hasDebts
              ? "Ver meu plano de resgate"
              : "Ir para o dashboard"}
        </Button>
      </div>
    );
  }

  // ─── Main render ───────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-50 bg-white overflow-y-auto">
      <div className="min-h-screen flex flex-col px-4 py-8 sm:px-6">
        {/* Header with back button and progress */}
        <div className="w-full max-w-lg mx-auto">
          <div className="flex items-center mb-4">
            {step > 1 && (
              <button
                onClick={goBack}
                className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                Voltar
              </button>
            )}
          </div>
          <StepIndicator />
        </div>

        {/* Step content */}
        <div className="flex-1 flex items-start justify-center">
          <div className="w-full">
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
            {step === 4 && renderStep4()}
            {step === 5 && renderStep5()}
          </div>
        </div>
      </div>
    </div>
  );
}
