import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  listButtons,
  listMessages,
  resetShop,
  updateButton,
  updateMessage,
  type ShopMessage,
} from "@/lib/admin-api";

function MessageCard({ message }: { message: ShopMessage }) {
  const qc = useQueryClient();
  const [text, setText] = useState(message.text);
  const [mode, setMode] = useState(message.parse_mode);
  const save = useMutation({
    mutationFn: () => updateMessage(message.key, text, mode),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-messages"] }),
  });
  const dirty = text !== message.text || mode !== message.parse_mode;
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-muted-foreground">{message.key}</span>
          <select className="rounded-md border bg-transparent px-2 text-xs" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="Markdown">Markdown</option>
            <option value="HTML">HTML</option>
          </select>
        </div>
        <textarea className="min-h-24 w-full rounded-md border bg-transparent p-2 text-sm" value={text} onChange={(e) => setText(e.target.value)} />
        <Button size="sm" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "…" : "ذخیره"}
        </Button>
      </CardContent>
    </Card>
  );
}

function MessagesTab() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-messages"], queryFn: listMessages });
  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-3">
      {data?.map((m) => <MessageCard key={m.key} message={m} />)}
    </div>
  );
}

function ButtonsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-buttons"], queryFn: listButtons });
  const inv = () => qc.invalidateQueries({ queryKey: ["admin-buttons"] });
  const toggle = useMutation({ mutationFn: (p: { id: number; on: boolean }) => updateButton(p.id, { is_enabled: !p.on }), onSuccess: inv });
  const rename = useMutation({ mutationFn: (p: { id: number; text: string }) => updateButton(p.id, { text: p.text }), onSuccess: inv });
  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-2">
      {data?.map((b) => (
        <Card key={b.id}><CardContent className="flex flex-wrap items-center justify-between gap-2 p-3">
          <div>
            <span className="font-bold">{b.emoji} {b.text}</span>
            <span className="text-xs text-muted-foreground"> · {b.menu} · {b.action}</span>{" "}
            {!b.is_enabled && <Badge variant="destructive">خاموش</Badge>}
          </div>
          <div className="flex gap-1">
            <Button size="sm" variant="outline" onClick={() => { const t = prompt("متن دکمه:", b.text); if (t != null) rename.mutate({ id: b.id, text: t }); }}>متن</Button>
            <Button size="sm" variant="secondary" onClick={() => toggle.mutate({ id: b.id, on: b.is_enabled })}>{b.is_enabled ? "خاموش" : "روشن"}</Button>
          </div>
        </CardContent></Card>
      ))}
    </div>
  );
}

export function ShopPage() {
  const qc = useQueryClient();
  const reset = useMutation({
    mutationFn: () => resetShop(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-messages"] }); qc.invalidateQueries({ queryKey: ["admin-buttons"] }); alert("به حالت پیش‌فرض بازگشت"); },
  });
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">شخصی‌سازی فروشگاه</h1>
        <Button variant="destructive" size="sm" onClick={() => { if (confirm("بازگردانی همه پیام‌ها و دکمه‌ها به پیش‌فرض؟")) reset.mutate(); }}>
          بازنشانی پیش‌فرض
        </Button>
      </div>
      <Tabs defaultValue="messages">
        <TabsList>
          <TabsTrigger value="messages">پیام‌ها</TabsTrigger>
          <TabsTrigger value="buttons">دکمه‌ها</TabsTrigger>
        </TabsList>
        <TabsContent value="messages" className="pt-4"><MessagesTab /></TabsContent>
        <TabsContent value="buttons" className="pt-4"><ButtonsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
