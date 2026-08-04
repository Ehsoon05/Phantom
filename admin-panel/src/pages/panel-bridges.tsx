import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cable, RefreshCw, Save, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  createPanelBridgeRule,
  deletePanelBridgeRule,
  getPanelBridgeContext,
  getPanelLiveInbounds,
  listPanelBridgeRules,
  syncPanelBridgeRule,
  updatePanelBridgeRule,
  type PanelBridgeRule,
  type PanelBridgeRuleInput,
} from "@/lib/admin-api";

type FormState = PanelBridgeRuleInput & { id: number | null };

const emptyForm: FormState = {
  id: null,
  name: "",
  source_panel_keys: [],
  source_category_keys: [],
  source_plan_ids: [],
  target_panel_key: "",
  target_inbounds: {},
  cleanup_on_delete: true,
  apply_now: true,
};

function toggleValue<T>(values: T[], value: T) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function statusLabel(value: string) {
  return {
    idle: "آماده",
    queued: "در صف",
    running: "در حال همگام‌سازی",
    completed: "تکمیل‌شده",
    completed_with_errors: "تکمیل با خطا",
    cleaning: "در حال پاک‌سازی",
    cleanup_failed: "پاک‌سازی ناقص",
  }[value] ?? value;
}

export function PanelBridgesPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(emptyForm);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const { data: context } = useQuery({ queryKey: ["panel-bridge-context"], queryFn: getPanelBridgeContext });
  const { data: rules = [] } = useQuery({
    queryKey: ["panel-bridge-rules"],
    queryFn: listPanelBridgeRules,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((rule) => ["queued", "running", "cleaning"].includes(rule.sync_status)) ? 3000 : false,
  });
  const { data: inbounds = [], isFetching: loadingInbounds } = useQuery({
    queryKey: ["panel-live-inbounds", form.target_panel_key],
    queryFn: () => getPanelLiveInbounds(form.target_panel_key),
    enabled: Boolean(form.target_panel_key),
    staleTime: 0,
  });

  const selectedInboundKeys = useMemo(
    () => new Set(Object.entries(form.target_inbounds).flatMap(([protocol, tags]) => tags.map((tag) => `${protocol}\u0000${tag}`))),
    [form.target_inbounds],
  );

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["panel-bridge-rules"] });
  };
  const save = useMutation({
    mutationFn: () => {
      const { id, ...body } = form;
      return id ? updatePanelBridgeRule(id, body) : createPanelBridgeRule(body);
    },
    onSuccess: async () => {
      setMessage("قانون ذخیره شد و همگام‌سازی آغاز شد.");
      setError("");
      setForm(emptyForm);
      await invalidate();
    },
    onError: (reason: Error) => setError(reason.message),
  });
  const sync = useMutation({
    mutationFn: syncPanelBridgeRule,
    onSuccess: invalidate,
    onError: (reason: Error) => setError(reason.message),
  });
  const remove = useMutation({
    mutationFn: deletePanelBridgeRule,
    onSuccess: async () => {
      setMessage("پاک‌سازی قانون آغاز شد؛ منبع کمکی از ساب‌ها و یوزرهای ساخته‌شده حذف می‌شوند.");
      await invalidate();
    },
    onError: (reason: Error) => setError(reason.message),
  });

  const editRule = (rule: PanelBridgeRule) => {
    setForm({
      id: rule.id,
      name: rule.name,
      source_panel_keys: rule.source_panel_keys,
      source_category_keys: rule.source_category_keys,
      source_plan_ids: rule.source_plan_ids,
      target_panel_key: rule.target_panel_key,
      target_inbounds: rule.target_inbounds,
      cleanup_on_delete: rule.cleanup_on_delete,
      apply_now: true,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const toggleInbound = (protocol: string, tag: string) => {
    const tags = toggleValue(form.target_inbounds[protocol] ?? [], tag);
    const target = { ...form.target_inbounds };
    if (tags.length) target[protocol] = tags;
    else delete target[protocol];
    setForm({ ...form, target_inbounds: target });
  };

  return (
    <div className="mx-auto grid max-w-6xl gap-6">
      <header className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary"><Cable /></span>
        <div><h1 className="text-xl font-bold">پنل‌ها و سرویس‌ها</h1><p className="text-sm text-muted-foreground">افزودن موقت خروجی یک پنل به سرویس‌های پنل، دسته یا پلن دیگر</p></div>
      </header>

      {(message || error) && <div className={`rounded-lg border p-3 text-sm ${error ? "border-destructive/40 bg-destructive/10 text-destructive" : "border-emerald-500/40 bg-emerald-500/10 text-emerald-600"}`}>{error || message}</div>}

      <section className="grid gap-5 rounded-lg border bg-card p-4 md:p-6">
        <div className="flex items-center justify-between gap-3"><h2 className="font-semibold">{form.id ? "ویرایش قانون" : "قانون جدید"}</h2>{form.id && <Button variant="ghost" size="sm" onClick={() => setForm(emptyForm)}>لغو ویرایش</Button>}</div>
        <label className="grid gap-2 text-sm">نام قانون<Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="مثلا اتصال موقت Mexico" /></label>

        <div className="grid gap-5 lg:grid-cols-3">
          <Selector title="پنل‌های مبدا" items={(context?.panels ?? []).map((item) => ({ value: item.key, label: item.title }))} selected={form.source_panel_keys} onToggle={(value) => setForm({ ...form, source_panel_keys: toggleValue(form.source_panel_keys, value) })} />
          <Selector title="دسته‌های مبدا" items={(context?.categories ?? []).map((item) => ({ value: item.key, label: item.title }))} selected={form.source_category_keys} onToggle={(value) => setForm({ ...form, source_category_keys: toggleValue(form.source_category_keys, value) })} />
          <Selector title="پلن‌های مبدا" items={(context?.plans ?? []).map((item) => ({ value: item.id, label: `${item.title} · ${item.category_key}` }))} selected={form.source_plan_ids} onToggle={(value) => setForm({ ...form, source_plan_ids: toggleValue(form.source_plan_ids, value) })} />
        </div>

        <label className="grid gap-2 text-sm">پنل مقصد
          <select className="h-10 rounded-md border bg-background px-3" value={form.target_panel_key} onChange={(event) => setForm({ ...form, target_panel_key: event.target.value, target_inbounds: {} })}>
            <option value="">انتخاب پنل مقصد</option>
            {(context?.panels ?? []).filter((item) => item.enabled).map((item) => <option key={item.key} value={item.key}>{item.title}</option>)}
          </select>
        </label>

        <div className="grid gap-2"><span className="text-sm">اینباندهای زنده مقصد</span>
          <div className="grid gap-2 md:grid-cols-2">
            {loadingInbounds && <span className="text-sm text-muted-foreground">در حال دریافت از پنل…</span>}
            {inbounds.map((item) => {
              const checked = selectedInboundKeys.has(`${item.protocol}\u0000${item.tag}`);
              return <label key={`${item.protocol}:${item.tag}`} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm ${checked ? "border-primary bg-primary/5" : ""}`}><input className="mt-1 size-4" type="checkbox" checked={checked} onChange={() => toggleInbound(item.protocol, item.tag)} /><span><strong className="block">{item.tag}</strong><small className="text-muted-foreground">{item.protocol} · {item.network || "-"} · پورت {item.port}</small></span></label>;
            })}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm"><input className="size-4" type="checkbox" checked={form.cleanup_on_delete} onChange={(event) => setForm({ ...form, cleanup_on_delete: event.target.checked })} /> هنگام حذف قانون، یوزرهای ساخته‌شده در پنل مقصد هم پاک شوند</label>
        <div className="flex justify-end"><Button disabled={save.isPending || !form.name || !form.target_panel_key} onClick={() => save.mutate()}><Save />ذخیره و اعمال</Button></div>
      </section>

      <section className="grid gap-3"><h2 className="font-semibold">قانون‌های فعال</h2>
        {rules.map((rule) => <article key={rule.id} className="grid gap-3 rounded-lg border bg-card p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><strong>{rule.name}</strong><div className="mt-1 flex flex-wrap gap-1"><Badge variant="outline">{statusLabel(rule.sync_status)}</Badge><Badge variant="secondary">{rule.assignments} اتصال فعال</Badge><Badge variant="outline">پورت {rule.target_ports.join(", ")}</Badge></div></div><div className="flex gap-2"><Button size="icon-sm" variant="outline" title="همگام‌سازی" onClick={() => sync.mutate(rule.id)}><RefreshCw /></Button><Button size="sm" variant="outline" onClick={() => editRule(rule)}>ویرایش</Button><Button size="icon-sm" variant="destructive" title="حذف و پاک‌سازی" onClick={() => window.confirm("این قانون و یوزرهای کمکی ساخته‌شده حذف شوند؟") && remove.mutate(rule.id)}><Trash2 /></Button></div></div>
          <div className="flex flex-wrap gap-1" aria-label="اینباندهای مقصد">
            {Object.entries(rule.target_inbounds).flatMap(([protocol, tags]) => tags.map((tag) => <Badge key={`${protocol}:${tag}`} variant="outline">{protocol.toUpperCase()} · {tag}</Badge>))}
          </div>
          <div className="grid grid-cols-2 gap-2 text-center text-sm sm:grid-cols-4"><Stat label="هدف" value={rule.total_matches} /><Stat label="موفق" value={rule.synced_count} /><Stat label="ردشده" value={rule.skipped_count} /><Stat label="خطا" value={rule.failed_count} /></div>
          {rule.last_error && <p className="rounded-md bg-destructive/10 p-2 text-xs text-destructive">{rule.last_error}</p>}
        </article>)}
        {!rules.length && <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">هنوز قانونی ساخته نشده است.</p>}
      </section>
    </div>
  );
}

function Selector<T extends string | number>({ title, items, selected, onToggle }: { title: string; items: { value: T; label: string }[]; selected: T[]; onToggle: (value: T) => void }) {
  return <div className="grid content-start gap-2"><span className="text-sm font-medium">{title}</span><div className="max-h-52 overflow-auto rounded-lg border p-2">{items.map((item) => <label key={String(item.value)} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-muted"><input className="size-4" type="checkbox" checked={selected.includes(item.value)} onChange={() => onToggle(item.value)} /><span>{item.label}</span></label>)}</div></div>;
}

function Stat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-md bg-muted/60 p-2"><strong className="block text-base">{value}</strong><span className="text-xs text-muted-foreground">{label}</span></div>;
}
