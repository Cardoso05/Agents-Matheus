interface Debt {
  id: string;
  name: string;
  current_balance: number;
  interest_rate: number;
  minimum_payment: number;
}

interface PayoffPlan {
  method: "avalanche" | "snowball";
  monthly_available: number;
  debts: PayoffDebtPlan[];
  total_interest_saved: number;
  estimated_debt_free_date: string;
}

interface PayoffDebtPlan {
  debt_id: string;
  name: string;
  monthly_payment: number;
  payoff_date: string;
  total_paid: number;
  total_interest: number;
  schedule: { month: string; payment: number; balance: number }[];
}

export function calculatePayoffPlan(
  debts: Debt[],
  monthlyAvailable: number,
  method: "avalanche" | "snowball"
): PayoffPlan {
  if (debts.length === 0) {
    return {
      method,
      monthly_available: monthlyAvailable,
      debts: [],
      total_interest_saved: 0,
      estimated_debt_free_date: new Date().toISOString(),
    };
  }

  // Sort debts
  const sorted = [...debts].sort((a, b) =>
    method === "avalanche"
      ? b.interest_rate - a.interest_rate  // highest interest first
      : a.current_balance - b.current_balance  // lowest balance first
  );

  const debtPlans: PayoffDebtPlan[] = sorted.map((d) => ({
    debt_id: d.id,
    name: d.name,
    monthly_payment: d.minimum_payment,
    payoff_date: "",
    total_paid: 0,
    total_interest: 0,
    schedule: [],
  }));

  // Simulate month by month
  const balances = sorted.map((d) => d.current_balance);
  const rates = sorted.map((d) => d.interest_rate);
  const minimums = sorted.map((d) => d.minimum_payment);
  const now = new Date();
  let month = 0;
  const MAX_MONTHS = 360; // 30 years cap

  while (balances.some((b) => b > 0) && month < MAX_MONTHS) {
    month++;
    const currentMonth = new Date(now.getFullYear(), now.getMonth() + month, 1);
    const monthStr = currentMonth.toISOString().split("T")[0];

    // Apply interest
    for (let i = 0; i < balances.length; i++) {
      if (balances[i] > 0) {
        const interest = balances[i] * rates[i];
        balances[i] += interest;
        debtPlans[i].total_interest += interest;
      }
    }

    // Allocate payments
    let remaining = monthlyAvailable;

    // Pay minimums first
    for (let i = 0; i < balances.length; i++) {
      if (balances[i] > 0) {
        const payment = Math.min(minimums[i], balances[i], remaining);
        balances[i] -= payment;
        remaining -= payment;
        debtPlans[i].total_paid += payment;
        debtPlans[i].schedule.push({
          month: monthStr,
          payment,
          balance: Math.max(0, balances[i]),
        });
      }
    }

    // Apply extra to first unpaid debt (avalanche/snowball order)
    for (let i = 0; i < balances.length; i++) {
      if (balances[i] > 0 && remaining > 0) {
        const extra = Math.min(remaining, balances[i]);
        balances[i] -= extra;
        remaining -= extra;
        debtPlans[i].total_paid += extra;
        const lastSchedule = debtPlans[i].schedule[debtPlans[i].schedule.length - 1];
        if (lastSchedule) {
          lastSchedule.payment += extra;
          lastSchedule.balance = Math.max(0, balances[i]);
        }
      }
    }

    // Record payoff dates
    for (let i = 0; i < balances.length; i++) {
      if (balances[i] <= 0 && !debtPlans[i].payoff_date) {
        debtPlans[i].payoff_date = monthStr;
      }
    }
  }

  // Calculate interest saved vs minimum-only
  const minOnlyInterest = calculateMinimumOnlyInterest(debts);
  const planInterest = debtPlans.reduce((s, d) => s + d.total_interest, 0);

  const lastPayoff = debtPlans
    .filter((d) => d.payoff_date)
    .sort((a, b) => b.payoff_date.localeCompare(a.payoff_date))[0];

  return {
    method,
    monthly_available: monthlyAvailable,
    debts: debtPlans,
    total_interest_saved: Math.max(0, minOnlyInterest - planInterest),
    estimated_debt_free_date: lastPayoff?.payoff_date || "",
  };
}

function calculateMinimumOnlyInterest(debts: Debt[]): number {
  let totalInterest = 0;
  const MAX_MONTHS = 360;

  for (const debt of debts) {
    let balance = debt.current_balance;
    for (let m = 0; m < MAX_MONTHS && balance > 0; m++) {
      const interest = balance * debt.interest_rate;
      balance += interest;
      totalInterest += interest;
      balance -= Math.min(debt.minimum_payment, balance);
    }
  }

  return totalInterest;
}
