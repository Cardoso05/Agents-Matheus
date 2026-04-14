"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  ArrowUpDown,
  Upload,
  CreditCard,
  PieChart,
  FileText,
  Settings,
  Bot,
  AlertTriangle,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/transactions", label: "Lançamentos", icon: ArrowUpDown },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/debts", label: "Plano de Quitação", icon: CreditCard },
  { href: "/emergency", label: "Emergência", icon: AlertTriangle, highlight: true },
  { href: "/budget", label: "Orçamento", icon: PieChart },
  { href: "/reports", label: "Relatórios", icon: FileText },
  { href: "/settings", label: "Configurações", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex flex-col w-64 bg-slate-900 text-white min-h-screen">
      <div className="flex items-center gap-2 px-6 py-5 border-b border-slate-700">
        <Bot className="h-7 w-7 text-sky-400" />
        <span className="text-xl font-bold">FinBot AI</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          const isHighlight = "highlight" in item && item.highlight;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? isHighlight
                    ? "bg-red-500/20 text-red-400"
                    : "bg-sky-500/20 text-sky-400"
                  : isHighlight
                    ? "text-red-300 hover:bg-red-900/30 hover:text-red-200"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t border-slate-700">
        <p className="text-xs text-slate-500">FinBot AI v1.0</p>
      </div>
    </aside>
  );
}
