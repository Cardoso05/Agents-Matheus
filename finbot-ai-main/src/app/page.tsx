import Link from "next/link";
import { Bot, TrendingUp, Shield, Zap } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between px-6 py-4 max-w-6xl mx-auto">
        <div className="flex items-center gap-2">
          <Bot className="h-7 w-7 text-sky-500" />
          <span className="text-xl font-bold">FinBot AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="px-4 py-2 text-sm font-medium hover:underline">
            Entrar
          </Link>
          <Link href="/signup" className="px-4 py-2 text-sm font-medium bg-sky-500 text-white rounded-lg hover:bg-sky-600">
            Criar conta
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
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">
            Faça upload dos seus extratos bancários e deixe a IA categorizar,
            analisar e criar um plano para quitar suas dívidas mais rápido.
          </p>
          <Link href="/signup" className="inline-block px-6 py-3 mt-4 text-sm font-medium bg-sky-500 text-white rounded-lg hover:bg-sky-600">
            Começar grátis
          </Link>
        </div>

        <div className="grid md:grid-cols-3 gap-8 mt-20">
          <div className="text-center space-y-3">
            <div className="mx-auto w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center">
              <Zap className="h-6 w-6 text-sky-500" />
            </div>
            <h3 className="font-semibold text-lg">Categorização automática</h3>
            <p className="text-sm text-gray-500">
              IA categoriza seus gastos automaticamente com base nos extratos bancários.
            </p>
          </div>
          <div className="text-center space-y-3">
            <div className="mx-auto w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
              <TrendingUp className="h-6 w-6 text-green-500" />
            </div>
            <h3 className="font-semibold text-lg">Plano de quitação</h3>
            <p className="text-sm text-gray-500">
              Compare métodos Avalanche vs Bola de Neve e veja quando ficará livre das dívidas.
            </p>
          </div>
          <div className="text-center space-y-3">
            <div className="mx-auto w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
              <Shield className="h-6 w-6 text-purple-500" />
            </div>
            <h3 className="font-semibold text-lg">Open Finance</h3>
            <p className="text-sm text-gray-500">
              Conecte seus bancos via Open Finance para sincronização automática.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
