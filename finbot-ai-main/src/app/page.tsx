import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Bot, TrendingUp, Shield, Zap } from "lucide-react";

export default async function HomePage() {
  let user = null;
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    user = data.user;
  } catch {
    // Supabase not configured yet — show landing page
  }

  if (user) {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between px-6 py-4 max-w-6xl mx-auto">
        <div className="flex items-center gap-2">
          <Bot className="h-7 w-7 text-sky-500" />
          <span className="text-xl font-bold">FinBot AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login">
            <Button variant="ghost">Entrar</Button>
          </Link>
          <Link href="/signup">
            <Button>Criar conta</Button>
          </Link>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center space-y-6">
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight">
            Suas finanças organizadas
            <br />
            <span className="text-sky-500">com inteligência artificial</span>
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Faça upload dos seus extratos bancários e deixe a IA categorizar,
            analisar e criar um plano para quitar suas dívidas mais rápido.
          </p>
          <Link href="/signup">
            <Button size="lg" className="mt-4">
              Começar grátis
            </Button>
          </Link>
        </div>

        <div className="grid md:grid-cols-3 gap-8 mt-20">
          <div className="text-center space-y-3">
            <div className="mx-auto w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center">
              <Zap className="h-6 w-6 text-sky-500" />
            </div>
            <h3 className="font-semibold text-lg">Categorização automática</h3>
            <p className="text-sm text-muted-foreground">
              IA categoriza seus gastos automaticamente com base nos extratos bancários.
            </p>
          </div>
          <div className="text-center space-y-3">
            <div className="mx-auto w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
              <TrendingUp className="h-6 w-6 text-green-500" />
            </div>
            <h3 className="font-semibold text-lg">Plano de quitação</h3>
            <p className="text-sm text-muted-foreground">
              Compare métodos Avalanche vs Bola de Neve e veja quando ficará livre das dívidas.
            </p>
          </div>
          <div className="text-center space-y-3">
            <div className="mx-auto w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
              <Shield className="h-6 w-6 text-purple-500" />
            </div>
            <h3 className="font-semibold text-lg">Open Finance</h3>
            <p className="text-sm text-muted-foreground">
              Conecte seus bancos via Open Finance para sincronização automática.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
