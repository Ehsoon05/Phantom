import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createMessageButton,
  deleteMessageButton,
  listMessageButtons,
  listButtons,
  listMessages,
  resetShop,
  updateButton,
  updateMessage,
  type ShopButton,
  type ShopMessage,
  type ShopMessageButton,
} from "@/lib/admin-api";

const MESSAGE_BUTTON_TYPES: Record<string, string> = {
  inline_url: "لینک شیشه‌ای",
  inline_copy: "کپی شیشه‌ای",
  inline_action: "اتصال به دکمه موجود",
};

function MessageButtonsEditor({
  message,
  buttons,
  shopButtons,
}: {
  message: ShopMessage;
  buttons: ShopMessageButton[];
  shopButtons: ShopButton[];
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    button_type: "inline_url",
    text: "",
    payload: "",
    source_button_id: "",
    row: "0",
    col: "0",
  });
  const inv = () => qc.invalidateQueries({ queryKey: ["admin-message-buttons"] });
  const create = useMutation({
    mutationFn: () =>
      createMessageButton({
        message_key: message.key,
        button_type: form.button_type,
        text: form.text,
        payload: form.payload || null,
        source_button_id: form.button_type === "inline_action" && form.source_button_id ? Number(form.source_button_id) : null,
        row: parseInt(form.row || "0", 10),
        col: parseInt(form.col || "0", 10),
      }),
    onSuccess: () => {
      setForm({ button_type: "inline_url", text: "", payload: "", source_button_id: "", row: "0", col: "0" });
      inv();
    },
  });
  const remove = useMutation({ mutationFn: (id: number) => deleteMessageButton(id), onSuccess: inv });

  return (
    <div className="space-y-2 rounded-md border p-2">
      <p className="text-xs font-semibold">دکمه‌های شیشه‌ای این پیام</p>
      <div className="space-y-1">
        {buttons.length === 0 && (
          <p className="text-xs text-muted-foreground">
            دکمه چندتایی ندارد. {message.response_button_type !== "text" ? `تنظیم قدیمی: ${message.response_button_type}` : ""}
          </p>
        )}
        {buttons.map((button) => {
          const linked = shopButtons.find((item) => item.id === button.source_button_id);
          return (
            <div key={button.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/50 px-2 py-1 text-xs">
              <span>
                <b>{button.text}</b>{" "}
                <span className="text-muted-foreground">
                  · {MESSAGE_BUTTON_TYPES[button.button_type] ?? button.button_type}
                  · ردیف {button.row} / ستون {button.col}
                  {button.payload ? ` · ${button.payload}` : ""}
                  {linked ? ` · اکشن: ${linked.text} (${linked.action})` : ""}
                </span>
              </span>
              <Button size="sm" variant="destructive" onClick={() => { if (confirm("حذف دکمه شیشه‌ای؟")) remove.mutate(button.id); }}>
                حذف
              </Button>
            </div>
          );
        })}
      </div>
      <div className="grid gap-2 md:grid-cols-6">
        <select className="rounded-md border bg-transparent px-2 text-xs" value={form.button_type} onChange={(e) => setForm({ ...form, button_type: e.target.value })}>
          <option value="inline_url">لینک</option>
          <option value="inline_copy">کپی</option>
          <option value="inline_action">اکشن دکمه موجود</option>
        </select>
        <input className="rounded-md border bg-transparent px-2 text-xs" placeholder="متن دکمه" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
        <input className="rounded-md border bg-transparent px-2 text-xs md:col-span-2" placeholder="لینک/متن کپی مثل {link} یا {share_url}" value={form.payload} onChange={(e) => setForm({ ...form, payload: e.target.value })} />
        <input className="rounded-md border bg-transparent px-2 text-xs" placeholder="ردیف" inputMode="numeric" value={form.row} onChange={(e) => setForm({ ...form, row: e.target.value })} />
        <input className="rounded-md border bg-transparent px-2 text-xs" placeholder="ستون" inputMode="numeric" value={form.col} onChange={(e) => setForm({ ...form, col: e.target.value })} />
        {form.button_type === "inline_action" && (
          <select className="rounded-md border bg-transparent px-2 text-xs md:col-span-5" value={form.source_button_id} onChange={(e) => setForm({ ...form, source_button_id: e.target.value })}>
            <option value="">دکمه متصل را انتخاب کنید</option>
            {shopButtons.map((button) => (
              <option key={button.id} value={button.id}>{button.text} · {button.menu} · {button.action}</option>
            ))}
          </select>
        )}
        <Button size="sm" disabled={!form.text || create.isPending} onClick={() => create.mutate()}>
          افزودن دکمه
        </Button>
      </div>
    </div>
  );
}

function MessageCard({
  message,
  messageButtons,
  shopButtons,
}: {
  message: ShopMessage;
  messageButtons: ShopMessageButton[];
  shopButtons: ShopButton[];
}) {
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
        <MessageButtonsEditor message={message} buttons={messageButtons} shopButtons={shopButtons} />
      </CardContent>
    </Card>
  );
}

function MessagesTab() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-messages"], queryFn: listMessages });
  const { data: messageButtons, isLoading: isLoadingButtons } = useQuery({ queryKey: ["admin-message-buttons"], queryFn: () => listMessageButtons() });
  const { data: shopButtons, isLoading: isLoadingShopButtons } = useQuery({ queryKey: ["admin-buttons"], queryFn: listButtons });
  if (isLoading || isLoadingButtons || isLoadingShopButtons) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-3">
      {data?.map((m) => (
        <MessageCard
          key={m.key}
          message={m}
          messageButtons={(messageButtons ?? []).filter((button) => button.message_key === m.key)}
          shopButtons={shopButtons ?? []}
        />
      ))}
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
