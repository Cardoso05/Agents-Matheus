"use client";

import { useEffect, useState, useMemo } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { formatCurrency } from "@/lib/utils/currency";
import { calculatePayoffPlan } from "@/lib/ai/payoff-plan";
import {
  Plus,
  CreditCard,
  Target,
  TrendingDown,
  Trophy,
  Clock,
  CheckCircle2,
  Zap,
  DollarSign,
} from "lucide-react";
import { toast } from "sonner";
import { PayoffTimeline } from "@/components/debts/payoff-timeline";
import { DebtCostBar } from "@/components/debts/debt-cost-bar";
import { PaymentDialog } from "@/components/debts/payment-dialog";

interface Debt {
  id: string;
  name: string;
  creditor: string | null;
  original_amount: number;
  current_balance: number;
  interest_rate: number;
  minimum_payment: number;
  installment_amount: number | null;
  remaining_installments: number | null;
  due_day: number | null;
  priority: number | null;
  status: string;
  notes: string | null;
}

export default function DebtsPage() {
  const [debts, setDebts] = useState<Debt[]>([]);
  const [loading, setLoading] = useState(true);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);
  const [selectedDebt, setSelectedDebt] = useState<Debt | null>(null);
  const [suggestedAmount, setSuggestedAmount] = useState(0);
  const [extraPayment, setExtraPayment] = useState([0]);
  const supabase = createClient();

  async function fetchDebts() {
    const { data } = await supabase
      .from("debts")
      .select("*")
      .order("priority", { ascending: true });
    setDebts((data as Debt[]) || []);
    setLoading(false);
  }

  useEffect(() => {
    fetchDebts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAddDebt(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);

    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) {
      toast.error("Sessão expirada. Faça login novamente.");
      return;
    }

    const { error } = await supabase.from("debts").insert({
      user_id: user.id,
      name: form.get("name") as string,
      creditor: (form.get("creditor") as string) || null,
      original_amount: Number(form.get("original_amount")),
      current_balance: Number(form.get("current_balance")),
      interest_rate: Number(form.get("interest_rate")) / 100,
      minimum_payment: Number(form.get("minimum_payment")),
      due_day: form.get("due_day") ? Number(form.get("due_day")) : null,
    });

    if (error) {
      toast.error("Erro ao adicionar dívida");
      return;
    }

    toast.success("Dívida adicionada!");
    setAddDialogOpen(false);
    fetchDebts();
  }

  // Computed values
  const activeDebts = debts.filter((d) => d.status === "active");
  const paidDebts = debts.filter((d) => d.status === "paid_off");

  const totalOriginal = debts.reduce(
    (s, d) => s + Number(d.original_amount),
    0
  );
  const totalCurrentBalance = activeDebts.reduce(
    (s, d) => s + Number(d.current_balance),
    0
  );
  const totalPaidOff = debts.reduce((s, d) => {
    const orig = Number(d.original_amount);
    const curr = Number(d.current_balance);
    return s + Math.max(0, orig - curr);
  }, 0);

  const overallProgress =
    totalOriginal > 0 ? (totalPaidOff / totalOriginal) * 100 : 0;

  const mappedActiveDebts = useMemo(
    () =>
      activeDebts.map((d) => ({
        ...d,
        current_balance: Number(d.current_balance),
        interest_rate: Number(d.interest_rate),
        minimum_payment: Number(d.minimum_payment),
      })),
    [activeDebts]
  );

  const totalMinimum = mappedActiveDebts.reduce(
    (s, d) => s + d.minimum_payment,
    0
  );
  const monthlyAvailable = totalMinimum + extraPayment[0];

  const plan = useMemo(
    () =>
      calculatePayoffPlan(mappedActiveDebts, monthlyAvailable, "avalanche"),
    [mappedActiveDebts, monthlyAvailable]
  );

  // Priority debt (first in plan)
  const priorityDebtPlan = plan.debts.length > 0 ? plan.debts[0] : null;
  const priorityDebt = priorityDebtPlan
    ? activeDebts.find((d) => d.id === priorityDebtPlan.debt_id)
    : null;

  const otherDebts = priorityDebt
    ? activeDebts.filter((d) => d.id !== priorityDebt.id)
    : activeDebts;

  // Extra payment allocated to priority debt
  const priorityExtra =
    priorityDebtPlan && priorityDebt
      ? Math.max(
          0,
          monthlyAvailable -
            totalMinimum
        )
      : 0;

  // Timeline milestones
  const timelineMilestones = useMemo(() => {
    if (plan.debts.length === 0) return [];

    const now = new Date();

    const milestones = [];

    // Current month marker
    milestones.push({
      month: 0,
      monthLabel: new Date().toLocaleDateString("pt-BR", {
        month: "long",
        year: "numeric",
      }),
      debtName: "",
      isCurrent: true,
      isFinal: false,
    });

    // Payoff milestones
    const sortedPayoffs = [...plan.debts]
      .filter((d) => d.payoff_date)
      .sort((a, b) => a.payoff_date.localeCompare(b.payoff_date));

    sortedPayoffs.forEach((debtPlan, index) => {
      const payoffDate = new Date(debtPlan.payoff_date);
      const monthsDiff =
        (payoffDate.getFullYear() - now.getFullYear()) * 12 +
        (payoffDate.getMonth() - now.getMonth());

      const nextDebt =
        index < sortedPayoffs.length - 1 ? sortedPayoffs[index + 1] : null;

      const isLast = index === sortedPayoffs.length - 1;

      milestones.push({
        month: monthsDiff,
        monthLabel: payoffDate.toLocaleDateString("pt-BR", {
          month: "long",
          year: "numeric",
        }),
        debtName: debtPlan.name,
        isCurrent: false,
        isFinal: false,
        freedPayment: debtPlan.monthly_payment,
        nextDebtName: nextDebt?.name,
      });

      // Final milestone
      if (isLast) {
        milestones.push({
          month: monthsDiff,
          monthLabel: payoffDate.toLocaleDateString("pt-BR", {
            month: "long",
            year: "numeric",
          }),
          debtName: "",
          isCurrent: false,
          isFinal: true,
        });
      }
    });

    return milestones;
  }, [plan]);

  // Remaining months
  const estimatedMonths = useMemo(() => {
    if (!plan.estimated_debt_free_date) return 0;
    const target = new Date(plan.estimated_debt_free_date);
    const now = new Date();
    return Math.max(
      0,
      (target.getFullYear() - now.getFullYear()) * 12 +
        (target.getMonth() - now.getMonth())
    );
  }, [plan.estimated_debt_free_date]);

  function openPaymentDialog(debt: Debt, amount: number) {
    setSelectedDebt(debt);
    setSuggestedAmount(amount);
    setPaymentDialogOpen(true);
  }

  // Preset scenarios for simulator
  function applyPreset(value: number) {
    setExtraPayment([value]);
  }

  return (
    <div className="space-y-8">
      {/* Header with Add button */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Plano de Quitação</h1>
          <p className="text-muted-foreground">
            Seu plano ativo de resgate financeiro
          </p>
        </div>
        <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Adicionar Dívida
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Nova Dívida</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleAddDebt} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Nome</Label>
                <Input
                  id="name"
                  name="name"
                  placeholder="Ex: Cartão Nubank"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="creditor">Credor</Label>
                <Input
                  id="creditor"
                  name="creditor"
                  placeholder="Ex: Nubank"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="original_amount">Valor Original</Label>
                  <Input
                    id="original_amount"
                    name="original_amount"
                    type="number"
                    step="0.01"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="current_balance">Saldo Atual</Label>
                  <Input
                    id="current_balance"
                    name="current_balance"
                    type="number"
                    step="0.01"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="interest_rate">Juros Mensal (%)</Label>
                  <Input
                    id="interest_rate"
                    name="interest_rate"
                    type="number"
                    step="0.01"
                    placeholder="1.99"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="minimum_payment">Pagamento Mínimo</Label>
                  <Input
                    id="minimum_payment"
                    name="minimum_payment"
                    type="number"
                    step="0.01"
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="due_day">Dia do Vencimento</Label>
                <Input
                  id="due_day"
                  name="due_day"
                  type="number"
                  min="1"
                  max="31"
                />
              </div>
              <Button type="submit" className="w-full">
                Salvar
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-32 animate-pulse bg-slate-100 rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : debts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
            <CreditCard className="h-12 w-12 text-slate-300" />
            <p className="text-muted-foreground">Nenhuma dívida cadastrada</p>
            <Button
              variant="outline"
              onClick={() => setAddDialogOpen(true)}
            >
              Adicionar primeira dívida
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* ===== Section 1: Resumo de Combate ===== */}
          <Card className="border-2 border-sky-200 bg-gradient-to-br from-sky-50 to-white">
            <CardContent className="p-6 space-y-5">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-sky-900 flex items-center gap-2">
                    <Trophy className="h-5 w-5 text-amber-500" />
                    Resumo de Combate
                  </h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Dívida total:{" "}
                    <span className="font-bold text-red-600">
                      {formatCurrency(totalCurrentBalance)}
                    </span>{" "}
                    {"\u2192"} Meta: R$ 0{" "}
                    {plan.estimated_debt_free_date && (
                      <>
                        até{" "}
                        <span className="font-semibold text-sky-700">
                          {new Date(
                            plan.estimated_debt_free_date
                          ).toLocaleDateString("pt-BR", {
                            month: "long",
                            year: "numeric",
                          })}
                        </span>
                      </>
                    )}
                  </p>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-medium">Progresso geral</span>
                  <span className="font-bold text-sky-700">
                    {overallProgress.toFixed(1)}%
                  </span>
                </div>
                <Progress value={overallProgress} className="h-4" />
              </div>

              {totalPaidOff > 0 && (
                <p className="text-sm font-medium text-green-700 bg-green-50 rounded-lg px-3 py-2">
                  {"\u{1F389}"} Você já eliminou{" "}
                  {formatCurrency(totalPaidOff)} em dívidas!
                </p>
              )}

              <div className="grid grid-cols-3 gap-4 pt-2">
                <div className="text-center">
                  <div className="flex items-center justify-center mb-1">
                    <TrendingDown className="h-4 w-4 text-green-600" />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Juros economizados
                  </p>
                  <p className="font-bold text-green-600">
                    {formatCurrency(plan.total_interest_saved)}
                  </p>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center mb-1">
                    <CheckCircle2 className="h-4 w-4 text-sky-600" />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Dívidas quitadas
                  </p>
                  <p className="font-bold text-sky-700">
                    {paidDebts.length} de {debts.length}
                  </p>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center mb-1">
                    <Clock className="h-4 w-4 text-amber-600" />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Tempo restante
                  </p>
                  <p className="font-bold text-amber-700">
                    {estimatedMonths > 0
                      ? `${estimatedMonths} ${estimatedMonths === 1 ? "mês" : "meses"}`
                      : "-"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ===== Section 2: Ação do Mês ===== */}
          {priorityDebt && (
            <div className="space-y-3">
              <h2 className="text-lg font-bold flex items-center gap-2">
                <Zap className="h-5 w-5 text-sky-500" />
                Ação do Mês
              </h2>

              {/* Priority debt card */}
              <Card className="border-2 border-sky-500 bg-sky-50/50">
                <CardContent className="p-6 space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-medium text-sky-700">
                        {"\u{1F3AF}"} Este mês, foque em:
                      </p>
                      <h3 className="text-xl font-bold">
                        {priorityDebt.name}
                      </h3>
                      {priorityDebt.creditor && (
                        <p className="text-sm text-muted-foreground">
                          {priorityDebt.creditor}
                        </p>
                      )}
                    </div>
                    <Badge variant="destructive">Prioridade #1</Badge>
                  </div>

                  <div className="bg-white rounded-lg p-4 space-y-2">
                    <p className="text-lg font-bold">
                      Pague{" "}
                      {formatCurrency(
                        Number(priorityDebt.minimum_payment) + priorityExtra
                      )}{" "}
                      {priorityDebt.due_day && (
                        <span className="text-sm font-normal text-muted-foreground">
                          até dia {priorityDebt.due_day}
                        </span>
                      )}
                    </p>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-muted-foreground">
                        {formatCurrency(Number(priorityDebt.minimum_payment))}{" "}
                        (mínimo)
                      </span>
                      {priorityExtra > 0 && (
                        <>
                          <span className="text-muted-foreground">+</span>
                          <span className="text-sky-600 font-semibold">
                            {formatCurrency(priorityExtra)} (ataque extra)
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  <Button
                    size="lg"
                    className="w-full"
                    onClick={() =>
                      openPaymentDialog(
                        priorityDebt,
                        Number(priorityDebt.minimum_payment) + priorityExtra
                      )
                    }
                  >
                    <DollarSign className="h-4 w-4 mr-2" />
                    Registrar Pagamento
                  </Button>
                </CardContent>
              </Card>

              {/* Other debts - pay minimum */}
              {otherDebts.length > 0 && (
                <div className="grid gap-2">
                  {otherDebts.map((debt) => (
                    <Card key={debt.id} className="border-slate-200">
                      <CardContent className="p-4 flex items-center justify-between">
                        <div>
                          <p className="text-sm text-muted-foreground">
                            Pague o mínimo em:
                          </p>
                          <p className="font-medium">{debt.name}</p>
                          <p className="text-sm font-semibold">
                            {formatCurrency(Number(debt.minimum_payment))}
                            {debt.due_day && (
                              <span className="text-muted-foreground font-normal ml-2">
                                até dia {debt.due_day}
                              </span>
                            )}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            openPaymentDialog(
                              debt,
                              Number(debt.minimum_payment)
                            )
                          }
                        >
                          Registrar Pagamento
                        </Button>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ===== Section 3: Custo Real da Dívida ===== */}
          {activeDebts.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-lg font-bold flex items-center gap-2">
                <Target className="h-5 w-5 text-red-500" />
                Custo Real da Dívida
              </h2>
              <div className="grid gap-4">
                {activeDebts.map((debt) => (
                  <Card key={debt.id}>
                    <CardContent className="p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold">{debt.name}</h3>
                        <span className="text-sm text-muted-foreground">
                          Juros: {(Number(debt.interest_rate) * 100).toFixed(2)}
                          %/mês
                        </span>
                      </div>
                      <DebtCostBar
                        originalAmount={Number(debt.original_amount)}
                        currentBalance={Number(debt.current_balance)}
                        interestRate={Number(debt.interest_rate)}
                        minimumPayment={Number(debt.minimum_payment)}
                      />
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* ===== Section 4: Timeline de Quitação ===== */}
          {timelineMilestones.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Clock className="h-5 w-5 text-sky-500" />
                  Timeline de Quitação
                </CardTitle>
              </CardHeader>
              <CardContent>
                <PayoffTimeline milestones={timelineMilestones} />
              </CardContent>
            </Card>
          )}

          {/* ===== Section 5: Simulador "E se..." ===== */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Zap className="h-5 w-5 text-amber-500" />
                Simulador &quot;E se...&quot;
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Preset buttons */}
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => applyPreset(500)}
                  className={
                    extraPayment[0] === 500
                      ? "border-sky-500 bg-sky-50"
                      : ""
                  }
                >
                  E se eu fizer um bico de R$ 500?
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => applyPreset(1000)}
                  className={
                    extraPayment[0] === 1000
                      ? "border-sky-500 bg-sky-50"
                      : ""
                  }
                >
                  E se eu vender algo por R$ 1.000?
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => applyPreset(250)}
                  className={
                    extraPayment[0] === 250
                      ? "border-sky-500 bg-sky-50"
                      : ""
                  }
                >
                  E se eu economizar R$ 250/mês?
                </Button>
              </div>

              {/* Slider */}
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm">Valor extra mensal</span>
                  <span className="text-sm font-semibold text-sky-600">
                    {formatCurrency(extraPayment[0])}
                  </span>
                </div>
                <Slider
                  value={extraPayment}
                  onValueChange={setExtraPayment}
                  max={5000}
                  step={50}
                />
              </div>

              {/* Results */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">
                    Pagamento Mensal
                  </p>
                  <p className="text-lg font-bold">
                    {formatCurrency(monthlyAvailable)}
                  </p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">
                    Data de Quitação
                  </p>
                  <p className="text-lg font-bold">
                    {plan.estimated_debt_free_date
                      ? new Date(
                          plan.estimated_debt_free_date
                        ).toLocaleDateString("pt-BR", {
                          month: "short",
                          year: "numeric",
                        })
                      : "-"}
                  </p>
                </div>
                <div className="bg-green-50 rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">
                    Economia em Juros
                  </p>
                  <p className="text-lg font-bold text-green-600">
                    {formatCurrency(plan.total_interest_saved)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Payment Dialog */}
      <PaymentDialog
        open={paymentDialogOpen}
        onOpenChange={setPaymentDialogOpen}
        debt={selectedDebt}
        suggestedAmount={suggestedAmount}
        onPaymentSaved={fetchDebts}
      />
    </div>
  );
}
