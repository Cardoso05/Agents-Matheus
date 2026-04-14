"use client";

import { Loader2, CheckCircle } from "lucide-react";

interface UploadProgressProps {
  progress: number;
  status: string;
}

export function UploadProgress({ progress, status }: UploadProgressProps) {
  return (
    <div className="flex flex-col items-center gap-3">
      {progress < 100 ? (
        <Loader2 className="h-8 w-8 text-sky-500 animate-spin" />
      ) : (
        <CheckCircle className="h-8 w-8 text-green-500" />
      )}
      <p className="text-sm text-muted-foreground">{status}</p>
      <div className="w-64 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-sky-500 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
