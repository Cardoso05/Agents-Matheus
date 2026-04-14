import { PluggyClient } from "./pluggy";
import { generateExternalId } from "@/lib/utils/dedup";

interface SyncResult {
  newTransactions: number;
  duplicates: number;
  accounts: number;
}

export async function syncOpenFinanceData(
  itemId: string,
  userId: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any
): Promise<SyncResult> {
  const pluggy = new PluggyClient();
  const accounts = await pluggy.getAccounts(itemId);

  let newTransactions = 0;
  let duplicates = 0;

  const now = new Date();
  const from = new Date(now.getFullYear(), now.getMonth() - 3, 1);

  for (const account of accounts) {
    // Upsert account
    await supabase.from("accounts").upsert(
      {
        user_id: userId,
        bank_slug: "open_finance",
        bank_name: account.name,
        account_type: account.type,
        balance: account.balance,
        open_finance_item_id: itemId,
        is_open_finance: true,
      },
      { onConflict: "open_finance_item_id" }
    );

    // Fetch transactions
    const transactions = await pluggy.getTransactions(account.id, from, now);

    for (const tx of transactions) {
      const externalId = tx.id || generateExternalId(tx.date, tx.amount, tx.description);

      // Check for duplicate
      const { data: existing } = await supabase
        .from("transactions")
        .select("id")
        .eq("external_id", externalId)
        .eq("user_id", userId)
        .single();

      if (existing) {
        duplicates++;
        continue;
      }

      await supabase.from("transactions").insert({
        user_id: userId,
        date: tx.date,
        amount: tx.amount,
        description: tx.description,
        type: tx.amount >= 0 ? "income" : "expense",
        source: "open_finance",
        external_id: externalId,
      });

      newTransactions++;
    }
  }

  // Update last sync
  await supabase
    .from("open_finance_connections")
    .update({ last_sync_at: new Date().toISOString() })
    .eq("item_id", itemId)
    .eq("user_id", userId);

  return {
    newTransactions,
    duplicates,
    accounts: accounts.length,
  };
}
