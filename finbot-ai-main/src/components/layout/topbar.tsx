"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Bell,
  LogOut,
  Settings,
  User,
  AlertTriangle,
  CalendarClock,
  TrendingUp,
  Wallet,
  Target,
  ArrowDownCircle,
  CheckCheck,
} from "lucide-react";
import Link from "next/link";

type AlertType =
  | "overspend"
  | "risk"
  | "due_date"
  | "saving_opportunity"
  | "goal_reached"
  | "low_income";

interface Alert {
  id: string;
  user_id: string;
  type: AlertType;
  title: string;
  message: string;
  metadata: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}

interface TopbarProps {
  userName?: string | null;
}

function getAlertIcon(type: AlertType) {
  switch (type) {
    case "due_date":
      return <CalendarClock className="h-5 w-5 text-red-600" />;
    case "overspend":
      return <TrendingUp className="h-5 w-5 text-amber-600" />;
    case "risk":
      return <AlertTriangle className="h-5 w-5 text-amber-600" />;
    case "saving_opportunity":
      return <Wallet className="h-5 w-5 text-emerald-600" />;
    case "goal_reached":
      return <Target className="h-5 w-5 text-emerald-600" />;
    case "low_income":
      return <ArrowDownCircle className="h-5 w-5 text-amber-600" />;
  }
}

function getAlertBgClass(type: AlertType, isRead: boolean) {
  if (isRead) return "bg-white";
  switch (type) {
    case "due_date":
      return "bg-red-50";
    case "overspend":
    case "risk":
      return "bg-amber-50";
    case "saving_opportunity":
    case "goal_reached":
      return "bg-emerald-50";
    case "low_income":
      return "bg-amber-50";
    default:
      return "bg-slate-50";
  }
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMin < 1) return "agora";
  if (diffMin < 60) return `${diffMin}min atrás`;
  if (diffHours < 24) return `${diffHours}h atrás`;
  if (diffDays === 1) return "ontem";
  if (diffDays < 7) return `${diffDays} dias atrás`;
  return date.toLocaleDateString("pt-BR");
}

export function Topbar({ userName }: TopbarProps) {
  const router = useRouter();
  const supabase = createClient();

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const initials = userName
    ? userName
        .split(" ")
        .map((n) => n[0])
        .join("")
        .slice(0, 2)
        .toUpperCase()
    : "U";

  const fetchAlerts = useCallback(async () => {
    const res = await fetch("/api/alerts");
    if (!res.ok) return;
    const json = await res.json();
    const data = (json.data ?? []) as Alert[];
    setAlerts(data);
    setUnreadCount(data.filter((a) => !a.is_read).length);
  }, []);

  // Fetch unread count on mount
  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  async function handleOpenSheet() {
    setSheetOpen(true);
    setLoading(true);
    try {
      // Trigger alert checking then refresh
      await fetch("/api/alerts", { method: "POST" });
      await fetchAlerts();
    } finally {
      setLoading(false);
    }
  }

  async function markAsRead(alertIds: string[]) {
    if (alertIds.length === 0) return;
    await fetch("/api/alerts", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alert_ids: alertIds }),
    });
    setAlerts((prev) =>
      prev.map((a) =>
        alertIds.includes(a.id) ? { ...a, is_read: true } : a
      )
    );
    setUnreadCount((prev) => Math.max(0, prev - alertIds.length));
  }

  async function markAllAsRead() {
    const unreadIds = alerts.filter((a) => !a.is_read).map((a) => a.id);
    await markAsRead(unreadIds);
  }

  async function handleAlertClick(alert: Alert) {
    if (!alert.is_read) {
      await markAsRead([alert.id]);
    }
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="flex items-center justify-between h-16 px-4 lg:px-6 border-b bg-white">
      <div className="lg:hidden">
        <span className="text-lg font-bold text-slate-900">FinBot AI</span>
      </div>

      <div className="hidden lg:block" />

      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          onClick={handleOpenSheet}
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </Badge>
          )}
        </Button>

        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetContent side="right" className="w-full sm:max-w-md p-0">
            <SheetHeader className="p-6 pb-2">
              <div className="flex items-center justify-between">
                <SheetTitle>Notificações</SheetTitle>
                {unreadCount > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-muted-foreground gap-1"
                    onClick={markAllAsRead}
                  >
                    <CheckCheck className="h-4 w-4" />
                    Marcar todas como lidas
                  </Button>
                )}
              </div>
              <SheetDescription>
                {unreadCount > 0
                  ? `Você tem ${unreadCount} notificação${unreadCount > 1 ? "ões" : ""} não lida${unreadCount > 1 ? "s" : ""}`
                  : "Nenhuma notificação nova"}
              </SheetDescription>
            </SheetHeader>

            <ScrollArea className="h-[calc(100vh-8rem)]">
              {loading ? (
                <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
                  Verificando alertas...
                </div>
              ) : alerts.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
                  <Bell className="h-10 w-10 mb-3 text-slate-300" />
                  Nenhuma notificação ainda
                </div>
              ) : (
                <div className="divide-y">
                  {alerts.map((alert) => (
                    <button
                      key={alert.id}
                      onClick={() => handleAlertClick(alert)}
                      className={`w-full text-left px-6 py-4 hover:bg-slate-50 transition-colors ${getAlertBgClass(alert.type, alert.is_read)}`}
                    >
                      <div className="flex gap-3">
                        <div className="flex-shrink-0 mt-0.5">
                          {getAlertIcon(alert.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p
                              className={`text-sm leading-tight ${
                                alert.is_read
                                  ? "font-normal text-slate-600"
                                  : "font-semibold text-slate-900"
                              }`}
                            >
                              {alert.title}
                            </p>
                            {!alert.is_read && (
                              <span className="flex-shrink-0 mt-1 h-2 w-2 rounded-full bg-sky-500" />
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1 leading-snug">
                            {alert.message}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1.5">
                            {timeAgo(alert.created_at)}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </SheetContent>
        </Sheet>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-sky-500 text-white text-sm">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <span className="hidden md:inline text-sm font-medium">
                {userName || "Usuário"}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href="/settings" className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Perfil
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/settings" className="flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Configurações
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleLogout}
              className="flex items-center gap-2 text-destructive"
            >
              <LogOut className="h-4 w-4" />
              Sair
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
