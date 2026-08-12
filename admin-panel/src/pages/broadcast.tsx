import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { sendBroadcast } from "@/lib/admin-api";

export function BroadcastPage() {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<string>("");
  const send = useMutation({
    mutationFn: () => sendBroadcast(text, mode || null),
    onSuccess: (r) => { alert(`پیام برای ${r.queued} کاربر در صف ارسال قرار گرفت`); setText(""); },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">پیام همگانی</h1>
      <Card><CardContent className="space-y-3 p-4">
        <textarea
          className="min-h-40 w-full rounded-md border bg-transparent p-3 text-sm"
          placeholder="متن پیام…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="flex items-center gap-2">
          <select className="rounded-md border bg-transparent px-2 py-1 text-sm" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="">بدون قالب</option>
            <option value="Markdown">Markdown</option>
            <option value="HTML">HTML</option>
          </select>
          <Button disabled={!text.trim() || send.isPending} onClick={() => { if (confirm("ارسال پیام به همه کاربران؟")) send.mutate(); }}>
            {send.isPending ? "در حال ارسال…" : "ارسال همگانی"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">پیام در پس‌زمینه برای همه کاربران غیرمسدود ارسال می‌شود.</p>
      </CardContent></Card>
    </div>
  );
}
