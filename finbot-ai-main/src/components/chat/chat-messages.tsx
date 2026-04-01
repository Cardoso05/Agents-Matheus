"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatMessages({ messages }: { messages: Message[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center space-y-2">
          <Bot className="h-10 w-10 text-sky-400 mx-auto" />
          <p className="text-sm font-medium">Olá! Sou o FinBot.</p>
          <p className="text-xs text-muted-foreground">
            Pergunte sobre suas finanças, gastos, dívidas ou peça dicas de economia.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 p-4">
      <div className="space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-sky-100 flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4 text-sky-500" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-sky-500 text-white"
                  : "bg-slate-100 text-slate-900"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm prose-slate max-w-none [&>p]:m-0 [&>p]:mb-2 [&>ul]:m-0 [&>ul]:mb-2 [&>ol]:m-0 [&>ol]:mb-2 [&>h1]:text-base [&>h1]:font-bold [&>h1]:mb-1 [&>h2]:text-sm [&>h2]:font-bold [&>h2]:mb-1 [&>h3]:text-sm [&>h3]:font-semibold [&>h3]:mb-1 [&>li]:m-0 [&>ul>li]:ml-4 [&>ol>li]:ml-4 [&_strong]:font-bold [&_em]:italic [&_code]:bg-slate-200 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                <User className="h-4 w-4 text-slate-500" />
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
