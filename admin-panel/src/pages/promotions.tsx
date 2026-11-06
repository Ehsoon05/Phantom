import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api";
import {
  createCoupon,
  createRule,
  deactivateCoupon,
  deleteCoupon,
  deleteRule,
  getReferralCommission,
  listCoupons,
  listRules,
  recalcReferrals,
  setReferralCommission,
  toggleRule,
} from "@/lib/admin-api";

const QUAL_LABELS: Record<string, string> = {
  joined: "عضو شد",
  wallet_charged: "کیف پول شارژ کرد",
  purchased: "خرید کرد",
  purchased_and_charged: "خرید + شارژ",
};

function CommissionCard() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["referral-commission"], queryFn: getReferralCommission });
  const [form, setForm] = useState({ enabled: true, percent: "15" });
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!data) return;
    setForm({ enabled: data.enabled, percent: String(data.percent) });
  }, [data]);

  const save = useMutation({
    mutationFn: () =>
      setReferralCommission({
        enabled: form.enabled,
        percent: Math.max(0, Math.min(100, parseInt(form.percent || "0", 10))),
      }),
    onSuccess: () => {
      setErr(null);
      qc.invalidateQueries({ queryKey: ["referral-commission"] });
    },
    onError: (e) => setErr(e instanceof ApiError ? e.message : "خطا"),
  });

  if (isLoading) return <Skeleton className="h-28 w-full rounded-xl" />;

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold">پورسانت مستقیم خرید زیرمجموعه</p>
            <p className="text-xs text-muted-foreground">
              این مقدار روی محاسبه واقعی کیف پول و متن دعوت دوستان اعمال می‌شود.
            </p>
          </div>
          <Badge variant={form.enabled ? "default" : "secondary"}>{form.enabled ? "فعال" : "غیرفعال"}</Badge>
        </div>
        <div className="grid gap-2 md:grid-cols-[1fr_160px_auto]">
          <label className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            پرداخت پورسانت فعال باشد
          </label>
          <Input
            placeholder="درصد پورسانت"
            inputMode="numeric"
            value={form.percent}
            onChange={(e) => setForm({ ...form, percent: e.target.value })}
          />
          <Button disabled={save.isPending || Number.isNaN(parseInt(form.percent, 10))} onClick={() => save.mutate()}>
            ذخیره پورسانت
          </Button>
        </div>
        {err && <p className="text-sm text-destructive">{err}</p>}
      </CardContent>
    </Card>
  );
}

function CouponsTab() {
  const qc = useQueryClient();
  const { data: coupons, isLoading } = useQuery({ queryKey: ["admin-coupons"], queryFn: listCoupons });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-coupons"] });
  const [form, setForm] = useState({ code: "", discount_type: "percent", amount: "" });
  const [err, setErr] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      createCoupon({ code: form.code, discount_type: form.discount_type, amount: parseInt(form.amount, 10), target_user_ids: null }),
    onSuccess: () => { setForm({ code: "", discount_type: "percent", amount: "" }); setErr(null); invalidate(); },
    onError: (e) => setErr(e instanceof ApiError ? e.message : "خطا"),
  });
  const deact = useMutation({ mutationFn: (c: string) => deactivateCoupon(c), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (c: string) => deleteCoupon(c), onSuccess: invalidate });

  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-4">
      <Card><CardContent className="grid grid-cols-2 gap-2 p-4 md:grid-cols-4">
        <Input placeholder="کد" dir="ltr" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
        <select className="rounded-md border bg-transparent px-2 text-sm" value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })}>
          <option value="percent">درصدی</option>
          <option value="fixed">مبلغ ثابت</option>
        </select>
        <Input placeholder={form.discount_type === "percent" ? "درصد" : "تومان"} inputMode="numeric" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
        <Button disabled={!form.code || !form.amount || create.isPending} onClick={() => create.mutate()}>ایجاد کوپن</Button>
      </CardContent></Card>
      {err && <p className="text-sm text-destructive">{err}</p>}
      <div className="space-y-2">
        {coupons?.map((c) => (
          <Card key={c.id}><CardContent className="flex flex-wrap items-center justify-between gap-2 p-3">
            <div className="space-y-1">
              <span className="font-bold" dir="ltr">{c.code}</span>{" "}
              <Badge variant="secondary">{c.discount_type === "percent" ? `${c.amount}%` : `${c.amount.toLocaleString("fa-IR")}ت`}</Badge>{" "}
              {!c.is_active && <Badge variant="destructive">غیرفعال</Badge>}
              <span className="text-xs text-muted-foreground"> · {c.applies_to_all ? "همه کاربران" : `${c.target_user_count} کاربر`}</span>
            </div>
            <div className="flex gap-1">
              {c.is_active && <Button size="sm" variant="secondary" onClick={() => deact.mutate(c.code)}>غیرفعال</Button>}
              <Button size="sm" variant="destructive" onClick={() => { if (confirm("حذف کوپن؟")) remove.mutate(c.code); }}>حذف</Button>
            </div>
          </CardContent></Card>
        ))}
      </div>
    </div>
  );
}

function RulesTab() {
  const qc = useQueryClient();
  const { data: rules, isLoading } = useQuery({ queryKey: ["admin-rules"], queryFn: listRules });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-rules"] });
  const [form, setForm] = useState({ title: "", qualification_type: "purchased", required_count: "", is_repeatable: false, reward_type: "wallet", wallet_amount: "", shop_plan_id: "" });
  const [err, setErr] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => createRule({
      title: form.title, qualification_type: form.qualification_type, required_count: parseInt(form.required_count, 10),
      is_repeatable: form.is_repeatable, reward_type: form.reward_type,
      wallet_amount: form.reward_type === "wallet" ? parseInt(form.wallet_amount, 10) : null,
      shop_plan_id: form.reward_type === "service" ? parseInt(form.shop_plan_id, 10) : null,
    }),
    onSuccess: () => { setErr(null); invalidate(); },
    onError: (e) => setErr(e instanceof ApiError ? e.message : "خطا"),
  });
  const toggle = useMutation({ mutationFn: (id: number) => toggleRule(id), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => deleteRule(id), onSuccess: invalidate });
  const recalc = useMutation({ mutationFn: () => recalcReferrals(), onSuccess: (r) => alert(`${r.grants} پاداش اعطا شد`) });

  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-4">
      <Card><CardContent className="space-y-2 p-4">
        <p className="text-sm font-semibold">قانون جدید پاداش دعوت</p>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          <Input placeholder="عنوان" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <select className="rounded-md border bg-transparent px-2 text-sm" value={form.qualification_type} onChange={(e) => setForm({ ...form, qualification_type: e.target.value })}>
            {Object.entries(QUAL_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <Input placeholder="تعداد لازم" inputMode="numeric" value={form.required_count} onChange={(e) => setForm({ ...form, required_count: e.target.value })} />
          <select className="rounded-md border bg-transparent px-2 text-sm" value={form.reward_type} onChange={(e) => setForm({ ...form, reward_type: e.target.value })}>
            <option value="wallet">پاداش کیف پول</option>
            <option value="service">پاداش سرویس</option>
          </select>
          {form.reward_type === "wallet"
            ? <Input placeholder="مبلغ (تومان)" inputMode="numeric" value={form.wallet_amount} onChange={(e) => setForm({ ...form, wallet_amount: e.target.value })} />
            : <Input placeholder="شناسه پلن" inputMode="numeric" value={form.shop_plan_id} onChange={(e) => setForm({ ...form, shop_plan_id: e.target.value })} />}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_repeatable} onChange={(e) => setForm({ ...form, is_repeatable: e.target.checked })} /> تکرارشونده</label>
        </div>
        {err && <p className="text-sm text-destructive">{err}</p>}
        <div className="flex gap-2">
          <Button disabled={!form.title || !form.required_count || create.isPending} onClick={() => create.mutate()}>ایجاد قانون</Button>
          <Button variant="secondary" disabled={recalc.isPending} onClick={() => recalc.mutate()}>بازمحاسبه پاداش‌ها</Button>
        </div>
      </CardContent></Card>
      <div className="space-y-2">
        {rules?.map((r) => (
          <Card key={r.id}><CardContent className="flex flex-wrap items-center justify-between gap-2 p-3">
            <div>
              <span className="font-bold">{r.title}</span>{" "}
              {!r.is_active && <Badge variant="destructive">غیرفعال</Badge>}
              <p className="text-xs text-muted-foreground">{QUAL_LABELS[r.qualification_type] ?? r.qualification_type} × {r.required_count} → {r.reward_type === "wallet" ? `${(r.wallet_amount ?? 0).toLocaleString("fa-IR")}ت` : `پلن ${r.shop_plan_id}`}{r.is_repeatable ? " · تکرارشونده" : ""}</p>
            </div>
            <div className="flex gap-1">
              <Button size="sm" variant="secondary" onClick={() => toggle.mutate(r.id)}>{r.is_active ? "غیرفعال" : "فعال"}</Button>
              <Button size="sm" variant="destructive" onClick={() => { if (confirm("حذف قانون؟")) remove.mutate(r.id); }}>حذف</Button>
            </div>
          </CardContent></Card>
        ))}
      </div>
    </div>
  );
}

export function PromotionsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">تخفیف‌ها و دعوت</h1>
      <CommissionCard />
      <Tabs defaultValue="coupons">
        <TabsList>
          <TabsTrigger value="coupons">کوپن‌ها</TabsTrigger>
          <TabsTrigger value="rules">قوانین دعوت</TabsTrigger>
        </TabsList>
        <TabsContent value="coupons" className="pt-4"><CouponsTab /></TabsContent>
        <TabsContent value="rules" className="pt-4"><RulesTab /></TabsContent>
      </Tabs>
    </div>
  );
}
