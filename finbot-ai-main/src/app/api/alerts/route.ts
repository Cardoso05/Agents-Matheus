import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { checkAndCreateAlerts } from "@/lib/alerts";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("alerts")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false })
    .limit(50);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data });
}

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
  }

  try {
    await checkAndCreateAlerts(user.id, supabase);
  } catch (err) {
    console.error("Error checking alerts:", err);
    return NextResponse.json(
      { error: "Falha ao verificar alertas" },
      { status: 500 }
    );
  }

  // Return fresh count of unread alerts
  const { count } = await supabase
    .from("alerts")
    .select("*", { count: "exact", head: true })
    .eq("user_id", user.id)
    .eq("is_read", false);

  return NextResponse.json({ data: { new_alerts_count: count ?? 0 } });
}

export async function PATCH(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
  }

  const body = await request.json();
  const { alert_ids } = body as { alert_ids?: string[] };

  if (!alert_ids || !Array.isArray(alert_ids) || alert_ids.length === 0) {
    return NextResponse.json(
      { error: "alert_ids é obrigatório" },
      { status: 400 }
    );
  }

  const { error } = await supabase
    .from("alerts")
    .update({ is_read: true })
    .in("id", alert_ids)
    .eq("user_id", user.id);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
