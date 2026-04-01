import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
  }

  // Sync transactions from connected banks via Pluggy
  // Placeholder implementation
  return NextResponse.json({
    error: "Open Finance sync not yet configured.",
  }, { status: 501 });
}
