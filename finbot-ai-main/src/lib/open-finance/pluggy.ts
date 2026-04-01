interface PluggyAccount {
  id: string;
  name: string;
  type: string;
  balance: number;
  bankData: {
    transferNumber: string;
    closingBalance: number;
  };
}

interface PluggyTransaction {
  id: string;
  description: string;
  amount: number;
  date: string;
  category: string;
  type: string;
}

export class PluggyClient {
  private clientId: string;
  private clientSecret: string;
  private baseUrl = "https://api.pluggy.ai";
  private accessToken: string | null = null;

  constructor() {
    this.clientId = process.env.PLUGGY_CLIENT_ID || "";
    this.clientSecret = process.env.PLUGGY_CLIENT_SECRET || "";
  }

  private async authenticate(): Promise<string> {
    if (this.accessToken) return this.accessToken;

    const res = await fetch(`${this.baseUrl}/auth`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: this.clientId,
        clientSecret: this.clientSecret,
      }),
    });

    const data = await res.json();
    this.accessToken = data.apiKey;
    return this.accessToken!;
  }

  async createConnectToken(userId: string): Promise<string> {
    const token = await this.authenticate();
    const res = await fetch(`${this.baseUrl}/connect_token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-KEY": token,
      },
      body: JSON.stringify({ clientUserId: userId }),
    });

    const data = await res.json();
    return data.accessToken;
  }

  async getAccounts(itemId: string): Promise<PluggyAccount[]> {
    const token = await this.authenticate();
    const res = await fetch(`${this.baseUrl}/accounts?itemId=${itemId}`, {
      headers: { "X-API-KEY": token },
    });

    const data = await res.json();
    return data.results;
  }

  async getTransactions(
    accountId: string,
    from: Date,
    to: Date
  ): Promise<PluggyTransaction[]> {
    const token = await this.authenticate();
    const params = new URLSearchParams({
      accountId,
      from: from.toISOString().split("T")[0],
      to: to.toISOString().split("T")[0],
    });

    const res = await fetch(`${this.baseUrl}/transactions?${params}`, {
      headers: { "X-API-KEY": token },
    });

    const data = await res.json();
    return data.results;
  }

  async deleteItem(itemId: string): Promise<void> {
    const token = await this.authenticate();
    await fetch(`${this.baseUrl}/items/${itemId}`, {
      method: "DELETE",
      headers: { "X-API-KEY": token },
    });
  }
}
