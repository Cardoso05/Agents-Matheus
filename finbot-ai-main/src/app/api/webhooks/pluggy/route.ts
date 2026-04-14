import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  // Pluggy webhook handler
  // Receives ITEM_UPDATED events when new transactions are available
  const body = await request.json();
  const event = body.event;

  console.log("Pluggy webhook received:", event);

  // In production:
  // 1. Verify webhook signature
  // 2. Fetch new transactions from Pluggy
  // 3. Run categorization pipeline
  // 4. Update account balances

  return NextResponse.json({ received: true });
}
