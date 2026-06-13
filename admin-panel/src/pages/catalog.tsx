import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatToman } from "@/lib/api";
import {
  addConfigs,
  deleteCategory,
  deletePlan,
  getInventoryStock,
  listCategories,
  listPlans,
  setPlanPrice,
  updatePlan,
  upsertCategory,
  upsertPlan,
} from "@/lib/admin-api";

function PlansTab() {
  const qc = useQueryClient();
  const { data: plans, isLoading } = useQuery({ queryKey: ["admin-plans"], queryFn: listPlans });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-plans"] });

  const [form, setForm] = useState({ volume_gb: "", title: "", price: "", category_key: "default" });
  const create = useMutation({
    mutationFn: () =>
      upsertPlan({
        volume_gb: parseInt(form.volume_gb, 10),
        title: form.title,
        price: form.price ? parseInt(form.price, 10) : null,
        category_key: form.category_key || "default",
      }),
    onSuccess: () => {
      setForm({ volume_gb: "", title: "", price: "", category_key: "default" });
      invalidate();
    },
  });
  const price = useMutation({
    mutationFn: ({ id, p }: { id: number; p: number }) => setPlanPrice(id, p),
    onSuccess: invalidate,
  });
  const toggle = useMutation({
    mutationFn: (p: { id: number; is_active: boolean }) => updatePlan(p.id, { is_active: !p.is_active }),
    onSuccess: invalidate,
  });
  const remove = useMutation({ mutationFn: (id: number) => deletePlan(id), onSuccess: invalidate });

  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="grid grid-cols-2 gap-2 p-4 md:grid-cols-5">
          <Input placeholder="حجم (GB)" inputMode="numeric" value={form.volume_gb} onChange={(e) => setForm({ ...form, volume_gb: e.target.value })} />
          <Input placeholder="عنوان" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <Input placeholder="قیمت (تومان)" inputMode="numeric" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
          <Input placeholder="دسته" value={form.category_key} onChange={(e) => setForm({ ...form, category_key: e.target.value })} />
          <Button disabled={!form.volume_gb || !form.title || create.isPending} onClick={() => create.mutate()}>
            افزودن پلن
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="overflow-x-auto p-4">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b text-right text-xs text-muted-foreground">
                <th className="pb-2">عنوان</th><th className="pb-2">دسته</th><th className="pb-2">حجم</th>
                <th className="pb-2">قیمت</th><th className="pb-2">موجودی</th><th className="pb-2">وضعیت</th><th className="pb-2">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {plans?.map((p) => (
                <tr key={p.id} className="border-b last:border-0">
                  <td className="py-2">{p.emoji} {p.title}</td>
                  <td className="py-2 text-muted-foreground">{p.category_key}</td>
                  <td className="py-2">{p.volume_gb} GB</td>
                  <td className="py-2">{p.price != null ? formatToman(p.price) : "—"}</td>
                  <td className="py-2"><Badge variant={(p.stock ?? 0) <= 3 ? "destructive" : "secondary"}>{p.stock ?? 0}</Badge></td>
                  <td className="py-2">{p.is_active ? "✅" : "⛔"}</td>
                  <td className="flex flex-wrap gap-1 py-2">
                    <Button size="sm" variant="outline" onClick={() => { const v = prompt("قیمت جدید:", String(p.price ?? "")); const n = parseInt(v ?? "", 10); if (!Number.isNaN(n)) price.mutate({ id: p.id, p: n }); }}>قیمت</Button>
                    <Button size="sm" variant="secondary" onClick={() => toggle.mutate({ id: p.id, is_active: p.is_active })}>{p.is_active ? "غیرفعال" : "فعال"}</Button>
                    <Button size="sm" variant="destructive" onClick={() => { if (confirm("حذف پلن؟")) remove.mutate(p.id); }}>حذف</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function CategoriesTab() {
  const qc = useQueryClient();
  const { data: cats, isLoading } = useQuery({ queryKey: ["admin-categories"], queryFn: listCategories });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-categories"] });
  const [key, setKey] = useState("");
  const [title, setTitle] = useState("");
  const create = useMutation({ mutationFn: () => upsertCategory(key, title || undefined), onSuccess: () => { setKey(""); setTitle(""); invalidate(); } });
  const remove = useMutation({ mutationFn: (k: string) => deleteCategory(k), onSuccess: invalidate });

  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-4">
      <Card><CardContent className="grid grid-cols-3 gap-2 p-4">
        <Input placeholder="کلید (انگلیسی)" value={key} onChange={(e) => setKey(e.target.value)} />
        <Input placeholder="عنوان" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button disabled={!key || create.isPending} onClick={() => create.mutate()}>افزودن دسته</Button>
      </CardContent></Card>
      <div className="space-y-2">
        {cats?.map((c) => (
          <Card key={c.id}><CardContent className="flex items-center justify-between p-3">
            <span>{c.emoji} {c.title} <span className="text-xs text-muted-foreground">({c.key})</span></span>
            <Button size="sm" variant="destructive" onClick={() => { if (confirm("حذف دسته؟")) remove.mutate(c.key); }}>حذف</Button>
          </CardContent></Card>
        ))}
      </div>
    </div>
  );
}

function InventoryTab() {
  const qc = useQueryClient();
  const { data: stock, isLoading } = useQuery({ queryKey: ["admin-stock"], queryFn: getInventoryStock });
  const [volume, setVolume] = useState("");
  const [category, setCategory] = useState("default");
  const [links, setLinks] = useState("");
  const add = useMutation({
    mutationFn: () => addConfigs(parseInt(volume, 10), category || "default", links.split("\n").map((l) => l.trim()).filter(Boolean)),
    onSuccess: (r) => { alert(`${r.added} کانفیگ اضافه شد`); setLinks(""); qc.invalidateQueries({ queryKey: ["admin-stock"] }); },
  });

  return (
    <div className="space-y-4">
      <Card><CardContent className="space-y-2 p-4">
        <p className="text-sm font-semibold">افزودن کانفیگ</p>
        <div className="grid grid-cols-2 gap-2">
          <Input placeholder="حجم (GB)" inputMode="numeric" value={volume} onChange={(e) => setVolume(e.target.value)} />
          <Input placeholder="دسته" value={category} onChange={(e) => setCategory(e.target.value)} />
        </div>
        <textarea className="min-h-28 w-full rounded-md border bg-transparent p-2 text-sm" dir="ltr" placeholder="هر خط یک لینک ساب" value={links} onChange={(e) => setLinks(e.target.value)} />
        <Button disabled={!volume || !links.trim() || add.isPending} onClick={() => add.mutate()}>{add.isPending ? "در حال افزودن…" : "افزودن"}</Button>
      </CardContent></Card>
      {isLoading ? <Skeleton className="h-32 w-full rounded-xl" /> : (
        <Card><CardContent className="overflow-x-auto p-4">
          <table className="w-full text-sm"><thead><tr className="border-b text-right text-xs text-muted-foreground">
            <th className="pb-2">پلن</th><th className="pb-2">دسته</th><th className="pb-2">حجم</th><th className="pb-2">موجودی</th></tr></thead>
            <tbody>{stock?.map((s) => (
              <tr key={`${s.category_key}-${s.volume_gb}`} className="border-b last:border-0">
                <td className="py-2">{s.title}</td><td className="py-2 text-muted-foreground">{s.category_key}</td>
                <td className="py-2">{s.volume_gb} GB</td><td className="py-2"><Badge variant={s.available <= 3 ? "destructive" : "secondary"}>{s.available}</Badge></td>
              </tr>))}</tbody></table>
        </CardContent></Card>
      )}
    </div>
  );
}

export function CatalogPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">محصولات و انبار</h1>
      <Tabs defaultValue="plans">
        <TabsList>
          <TabsTrigger value="plans">پلن‌ها</TabsTrigger>
          <TabsTrigger value="categories">دسته‌ها</TabsTrigger>
          <TabsTrigger value="inventory">انبار</TabsTrigger>
        </TabsList>
        <TabsContent value="plans" className="pt-4"><PlansTab /></TabsContent>
        <TabsContent value="categories" className="pt-4"><CategoriesTab /></TabsContent>
        <TabsContent value="inventory" className="pt-4"><InventoryTab /></TabsContent>
      </Tabs>
    </div>
  );
}
