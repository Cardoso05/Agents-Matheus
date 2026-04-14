import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
  }

  // Pluggy Connect Widget integration placeholder
  // In production, this would create a connect token via Pluggy API
  return NextResponse.json({
    error: "Open Finance integration not yet configured. Set PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET.",
  }, { status: 501 });
}
