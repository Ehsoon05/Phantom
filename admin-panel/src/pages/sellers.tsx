import {
  CircleDollarSign,
  PackagePlus,
  Pencil,
  Plus,
  Search,
  Server,
  ShieldCheck,
  Store,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  adjustSellerBalance,
  createSeller,
  createSellerOffer,
  deleteSellerBuiltService,
  deleteSellerOffer,
  getSellerSummary,
  listSellerBuiltServices,
  listSellerOffers,
  listSellerPanels,
  listSellers,
  type SellerAccount,
  type SellerBuiltService,
  type SellerOffer,
  type SellerPanelOption,
  type SellerSummary,
  updateSeller,
  updateSellerOffer,
} from "@/lib/admin-api";

const toman = (value: number) => `${new Intl.NumberFormat("fa-IR").format(value)} تومان`;

const emptyOffer = {
  title: "",
  panel_key: "",
  price_toman: 0,
  volume_gb: 20,
  lock_volume: false,
  default_duration_days: 30,
  allowed_time_modes: ["date"],
  default_time_mode: "date",
  lock_time_mode: false,
  lock_duration: false,
  name_prefix: "PhantomSeller_1",
  panel_hwid_limit: null as number | null,
  subscription_device_limit: 0,
  profile_title: "",
  support_url: "@PhantomHubs",
  show_header: true,
  show_config_preview: true,
  info_proxies_enabled: false,
  is_active: true,
};

type OfferForm = typeof emptyOffer;

function Field({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={wide ? "grid gap-1.5 md:col-span-2" : "grid gap-1.5"}>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Users }) {
  return (
    <div className="flex min-h-24 items-center gap-3 border-l border-border px-4 last:border-l-0">
      <span className="grid size-10 place-items-center rounded-md bg-primary/10 text-primary">
        <Icon className="size-5" />
      </span>
      <div className="grid gap-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <strong className="text-lg">{value}</strong>
      </div>
    </div>
  );
}

export function SellersPage() {
  const [summary, setSummary] = useState<SellerSummary | null>(null);
  const [sellers, setSellers] = useState<SellerAccount[]>([]);
  const [panels, setPanels] = useState<SellerPanelOption[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [offers, setOffers] = useState<SellerOffer[]>([]);
  const [builtServices, setBuiltServices] = useState<SellerBuiltService[]>([]);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showNewSeller, setShowNewSeller] = useState(false);
  const [showEditSeller, setShowEditSeller] = useState(false);
  const [showOffer, setShowOffer] = useState(false);
  const [editingOfferId, setEditingOfferId] = useState<number | null>(null);
  const [sellerForm, setSellerForm] = useState({
    username: "",
    display_name: "",
    password: "",
    initial_balance: 0,
    allow_negative_balance: false,
  });
  const [sellerEditForm, setSellerEditForm] = useState({
    username: "",
    display_name: "",
    password: "",
  });
  const [offerForm, setOfferForm] = useState<OfferForm>(emptyOffer);
  const selected = useMemo(
    () => sellers.find((seller) => seller.id === selectedId) ?? null,
    [sellers, selectedId],
  );

  const load = useCallback(async () => {
    const [sellerRows, metrics, panelRows] = await Promise.all([
      listSellers(query),
      getSellerSummary(),
      listSellerPanels(),
    ]);
    setSellers(sellerRows);
    setSummary(metrics);
    setPanels(panelRows);
    if (!selectedId && sellerRows[0]) setSelectedId(sellerRows[0].id);
  }, [query, selectedId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load().catch((reason) => setError(reason.message)), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([
      listSellerOffers(selectedId),
      listSellerBuiltServices(selectedId),
    ])
      .then(([offerRows, serviceRows]) => {
        setOffers(offerRows);
        setBuiltServices(serviceRows);
      })
      .catch((reason) => setError(reason.message));
  }, [selectedId]);

  async function submitSeller(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const value = await createSeller(sellerForm);
      setSellers((items) => [value, ...items]);
      setSelectedId(value.id);
      setSellerForm({ username: "", display_name: "", password: "", initial_balance: 0, allow_negative_balance: false });
      setShowNewSeller(false);
      setNotice("حساب همکار ساخته شد.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ساخت حساب انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  function openNewOffer() {
    setEditingOfferId(null);
    setOfferForm({
      ...emptyOffer,
      panel_key: panels[0]?.key ?? "",
      allowed_time_modes: ["date"],
    });
    setShowOffer(true);
  }

  function openEditOffer(offer: SellerOffer) {
    setEditingOfferId(offer.id);
    setOfferForm({
      title: offer.title,
      panel_key: offer.panel_key,
      price_toman: offer.price_toman,
      volume_gb: offer.volume_gb,
      lock_volume: offer.lock_volume,
      default_duration_days: offer.default_duration_days,
      allowed_time_modes: [...offer.allowed_time_modes],
      default_time_mode: offer.default_time_mode,
      lock_time_mode: offer.lock_time_mode,
      lock_duration: offer.lock_duration,
      name_prefix: offer.name_prefix,
      panel_hwid_limit: offer.panel_hwid_limit,
      subscription_device_limit: offer.subscription_device_limit,
      profile_title: offer.profile_title ?? "",
      support_url: offer.support_url ?? "",
      show_header: offer.show_header,
      show_config_preview: offer.show_config_preview,
      info_proxies_enabled: offer.info_proxies_enabled,
      is_active: offer.is_active,
    });
    setShowOffer(true);
  }

  async function submitOffer(event: FormEvent) {
    event.preventDefault();
    if (!selectedId) return;
    setBusy(true);
    setError("");
    try {
      if (editingOfferId) await updateSellerOffer(editingOfferId, offerForm);
      else await createSellerOffer(selectedId, offerForm);
      setOffers(await listSellerOffers(selectedId));
      setShowOffer(false);
      setNotice(editingOfferId ? "تنظیمات سرویس ذخیره شد." : "سرویس همکاری اضافه شد.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ذخیره انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function changeBalance() {
    if (!selected) return;
    const raw = window.prompt("مبلغ تغییر موجودی را وارد کنید؛ برای کسر با منفی وارد کنید:");
    if (!raw) return;
    const amount = Number(raw.replaceAll(",", ""));
    if (!Number.isSafeInteger(amount) || amount === 0) return;
    const description = window.prompt("شرح تراکنش:", "اصلاح موجودی توسط مدیر") || "اصلاح موجودی توسط مدیر";
    try {
      const updated = await adjustSellerBalance(selected.id, amount, description);
      setSellers((items) => items.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
      setNotice("موجودی همکار به‌روز شد.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تغییر موجودی انجام نشد.");
    }
  }

  async function toggleSeller() {
    if (!selected) return;
    const updated = await updateSeller(selected.id, { is_active: !selected.is_active });
    setSellers((items) => items.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
  }

  async function toggleNegativeBalance() {
    if (!selected) return;
    try {
      const updated = await updateSeller(selected.id, {
        allow_negative_balance: !selected.allow_negative_balance,
      });
      setSellers((items) => items.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
      setNotice(updated.allow_negative_balance ? "امکان بدهکارشدن همکار فعال شد." : "امکان بدهکارشدن همکار غیرفعال شد.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تغییر مجوز بدهکاری انجام نشد.");
    }
  }

  function openEditSeller() {
    if (!selected) return;
    setSellerEditForm({
      username: selected.username,
      display_name: selected.display_name,
      password: "",
    });
    setShowEditSeller(true);
  }

  async function submitSellerEdit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        username: sellerEditForm.username,
        display_name: sellerEditForm.display_name,
      };
      if (sellerEditForm.password) payload.password = sellerEditForm.password;
      const updated = await updateSeller(selected.id, payload);
      setSellers((items) => items.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
      setShowEditSeller(false);
      setNotice(sellerEditForm.password ? "نام کاربری و رمز همکار به‌روز شد." : "مشخصات همکار به‌روز شد.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ویرایش حساب همکار انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function removeBuiltService(service: SellerBuiltService) {
    if (!window.confirm(`یوزر «${service.panel_username}» از پنل سازنده و پنل ساب کاملاً حذف شود؟ این عملیات قابل بازگشت نیست.`)) return;
    try {
      await deleteSellerBuiltService(service.id);
      setBuiltServices((items) => items.filter((item) => item.id !== service.id));
      setNotice("یوزر از پنل سازنده و پنل ساب حذف شد.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "حذف یوزر انجام نشد.");
    }
  }

  const toggleMode = (mode: string) => {
    const values = offerForm.allowed_time_modes.includes(mode)
      ? offerForm.allowed_time_modes.filter((value) => value !== mode)
      : [...offerForm.allowed_time_modes, mode];
    if (!values.length) return;
    setOfferForm({
      ...offerForm,
      allowed_time_modes: values,
      default_time_mode: values.includes(offerForm.default_time_mode)
        ? offerForm.default_time_mode
        : values[0],
    });
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">همکاران فروش</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            حساب‌ها، موجودی و سرویس‌های اختصاصی هر همکار
          </p>
        </div>
        <Button onClick={() => setShowNewSeller(true)}>
          <UserPlus className="size-4" />
          همکار جدید
        </Button>
      </header>

      {(notice || error) && (
        <div className={`rounded-md border px-3 py-2 text-sm ${error ? "border-destructive/30 bg-destructive/10 text-destructive" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-600"}`}>
          {error || notice}
        </div>
      )}

      <section className="grid overflow-hidden rounded-lg border bg-card sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="کل همکاران" value={String(summary?.sellers ?? 0)} icon={Users} />
        <Metric label="همکار فعال" value={String(summary?.active_sellers ?? 0)} icon={ShieldCheck} />
        <Metric label="سرویس ساخته‌شده" value={String(summary?.services ?? 0)} icon={Store} />
        <Metric label="جمع فروش همکاری" value={toman(summary?.revenue ?? 0)} icon={CircleDollarSign} />
      </section>

      <div className="grid gap-4 xl:grid-cols-[310px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-lg border bg-card">
          <label className="relative block border-b p-3">
            <Search className="absolute right-6 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pr-9" placeholder="جست‌وجوی همکار..." value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <div className="max-h-[660px] overflow-y-auto p-2">
            {sellers.map((seller) => (
              <button
                key={seller.id}
                onClick={() => setSelectedId(seller.id)}
                className={`mb-1 flex w-full items-center justify-between rounded-md px-3 py-3 text-right transition-colors ${selectedId === seller.id ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
              >
                <div className="min-w-0">
                  <strong className="block truncate text-sm">{seller.display_name}</strong>
                  <span className={`block truncate text-xs ${selectedId === seller.id ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                    @{seller.username}
                  </span>
                </div>
                <span className={`text-xs font-bold ${seller.wallet_balance < 0 ? "text-destructive" : ""}`}>{toman(seller.wallet_balance)}</span>
              </button>
            ))}
            {!sellers.length && <p className="p-6 text-center text-sm text-muted-foreground">همکاری ثبت نشده است.</p>}
          </div>
        </aside>

        <main className="min-w-0 space-y-4">
          {selected ? (
            <>
              <section className="flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-card p-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-bold">{selected.display_name}</h2>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${selected.is_active ? "bg-emerald-500/10 text-emerald-600" : "bg-destructive/10 text-destructive"}`}>
                      {selected.is_active ? "فعال" : "غیرفعال"}
                    </span>
                    {selected.allow_negative_balance && <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-600">اعتبار منفی مجاز</span>}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    @{selected.username} · {selected.service_count ?? 0} سرویس ساخته‌شده
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={openEditSeller}>
                    <Pencil className="size-4" /> ویرایش ورود
                  </Button>
                  <Button variant="outline" onClick={changeBalance}>
                    <CircleDollarSign className="size-4" /> تغییر موجودی
                  </Button>
                  <Button variant="outline" onClick={toggleNegativeBalance}>
                    {selected.allow_negative_balance ? "بستن اعتبار منفی" : "اجازه اعتبار منفی"}
                  </Button>
                  <Button variant={selected.is_active ? "destructive" : "secondary"} onClick={toggleSeller}>
                    {selected.is_active ? "غیرفعال‌کردن حساب" : "فعال‌کردن حساب"}
                  </Button>
                </div>
              </section>

              <section className="overflow-hidden rounded-lg border bg-card">
                <div className="flex items-center justify-between border-b p-4">
                  <div>
                    <h2 className="font-bold">سرویس‌های قابل ساخت</h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      قیمت و تنظیمات این بخش فقط برای همین همکار است.
                    </p>
                  </div>
                  <Button size="sm" onClick={openNewOffer}><Plus className="size-4" /> افزودن سرویس</Button>
                </div>
                <div className="divide-y">
                  {offers.map((offer) => (
                    <article key={offer.id} className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong>{offer.title}</strong>
                          <span className="rounded bg-muted px-2 py-0.5 text-xs">{offer.panel_key}</span>
                          {offer.lock_volume && <span className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">حجم ثابت</span>}
                          {offer.lock_time_mode && <span className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">نوع تاریخ ثابت</span>}
                          {offer.lock_duration && <span className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">مدت ثابت</span>}
                          {!offer.is_active && <span className="rounded bg-destructive/10 px-2 py-0.5 text-xs text-destructive">غیرفعال</span>}
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {offer.volume_gb ? `${offer.volume_gb}GB` : "حجم نامحدود"} · {offer.default_duration_days || "نامحدود"} روز · محدودیت ساب {offer.subscription_device_limit || "نامحدود"}
                        </p>
                      </div>
                      <div className="flex items-center justify-between gap-3 md:justify-end">
                        <strong className="text-primary">{toman(offer.price_toman)}</strong>
                        <Button size="icon" variant="outline" title="ویرایش" onClick={() => openEditOffer(offer)}><Pencil className="size-4" /></Button>
                        <Button
                          size="icon"
                          variant="outline"
                          title="حذف"
                          onClick={async () => {
                            if (!window.confirm("این سرویس همکاری حذف یا غیرفعال شود؟")) return;
                            await deleteSellerOffer(offer.id);
                            setOffers(await listSellerOffers(selected.id));
                          }}
                        >
                          <Trash2 className="size-4 text-destructive" />
                        </Button>
                      </div>
                    </article>
                  ))}
                  {!offers.length && (
                    <div className="grid min-h-44 place-items-center p-6 text-center text-sm text-muted-foreground">
                      هنوز سرویسی برای این همکار تعریف نشده است.
                    </div>
                  )}
                </div>
              </section>

              <section className="overflow-hidden rounded-lg border bg-card">
                <div className="border-b p-4">
                  <h2 className="font-bold">یوزرهای ساخته‌شده</h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    حذف از این بخش، یوزر را از پنل سازنده و لینک را از پنل ساب پاک می‌کند.
                  </p>
                </div>
                <div className="divide-y">
                  {builtServices.map((service) => (
                    <article key={service.id} className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="grid size-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary"><Server className="size-4" /></span>
                        <div className="min-w-0">
                          <strong className="block truncate font-mono text-sm" dir="ltr">{service.panel_username}</strong>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {service.panel_key} · {service.volume_gb ? `${service.volume_gb}GB` : "حجم نامحدود"} · {service.duration_days ? `${service.duration_days} روز` : "زمان نامحدود"} · {service.status}
                          </p>
                        </div>
                      </div>
                      <Button size="icon" variant="outline" title="حذف کامل یوزر" onClick={() => void removeBuiltService(service)}>
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </article>
                  ))}
                  {!builtServices.length && <p className="p-8 text-center text-sm text-muted-foreground">هنوز یوزری توسط این همکار ساخته نشده است.</p>}
                </div>
              </section>
            </>
          ) : (
            <div className="grid min-h-96 place-items-center rounded-lg border bg-card text-sm text-muted-foreground">
              یک همکار را انتخاب کنید.
            </div>
          )}
        </main>
      </div>

      {showEditSeller && selected && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={(event) => event.target === event.currentTarget && setShowEditSeller(false)}>
          <form onSubmit={submitSellerEdit} className="w-full max-w-lg rounded-lg border bg-background p-5 shadow-2xl">
            <h2 className="text-lg font-bold">ویرایش دسترسی همکار</h2>
            <p className="mb-4 mt-1 text-xs text-muted-foreground">برای حفظ رمز فعلی، فیلد رمز جدید را خالی بگذارید.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="نام نمایشی"><Input required value={sellerEditForm.display_name} onChange={(event) => setSellerEditForm({ ...sellerEditForm, display_name: event.target.value })} /></Field>
              <Field label="نام کاربری ورود"><Input dir="ltr" required minLength={3} value={sellerEditForm.username} onChange={(event) => setSellerEditForm({ ...sellerEditForm, username: event.target.value })} /></Field>
              <Field label="رمز عبور جدید" wide><Input dir="ltr" type="password" minLength={8} placeholder="بدون تغییر" value={sellerEditForm.password} onChange={(event) => setSellerEditForm({ ...sellerEditForm, password: event.target.value })} /></Field>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setShowEditSeller(false)}>انصراف</Button>
              <Button type="submit" disabled={busy}><Pencil className="size-4" /> ذخیره تغییرات</Button>
            </div>
          </form>
        </div>
      )}

      {showNewSeller && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={(event) => event.target === event.currentTarget && setShowNewSeller(false)}>
          <form onSubmit={submitSeller} className="w-full max-w-lg rounded-lg border bg-background p-5 shadow-2xl">
            <h2 className="mb-4 text-lg font-bold">ساخت حساب همکار</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="نام نمایشی"><Input required value={sellerForm.display_name} onChange={(event) => setSellerForm({ ...sellerForm, display_name: event.target.value })} /></Field>
              <Field label="نام کاربری"><Input dir="ltr" required value={sellerForm.username} onChange={(event) => setSellerForm({ ...sellerForm, username: event.target.value })} /></Field>
              <Field label="رمز عبور"><Input dir="ltr" type="password" required minLength={8} value={sellerForm.password} onChange={(event) => setSellerForm({ ...sellerForm, password: event.target.value })} /></Field>
              <Field label="موجودی اولیه (تومان)"><Input dir="ltr" type="number" min={sellerForm.allow_negative_balance ? undefined : 0} value={sellerForm.initial_balance} onChange={(event) => setSellerForm({ ...sellerForm, initial_balance: Number(event.target.value) })} /></Field>
              <Field label="اعتبار حساب" wide>
                <label className="flex items-center gap-2 rounded-md border p-3 text-sm">
                  <input className="size-4" type="checkbox" checked={sellerForm.allow_negative_balance} onChange={(event) => setSellerForm({ ...sellerForm, allow_negative_balance: event.target.checked })} />
                  اجازه ساخت با موجودی منفی و ثبت بدهی
                </label>
              </Field>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setShowNewSeller(false)}>انصراف</Button>
              <Button type="submit" disabled={busy}><UserPlus className="size-4" /> ساخت حساب</Button>
            </div>
          </form>
        </div>
      )}

      {showOffer && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/65 p-3 sm:p-6">
          <form onSubmit={submitOffer} className="mx-auto w-full max-w-3xl rounded-lg border bg-background p-5 shadow-2xl">
            <div className="mb-5 flex items-center justify-between">
              <div><h2 className="text-lg font-bold">{editingOfferId ? "ویرایش سرویس همکاری" : "سرویس همکاری جدید"}</h2><p className="mt-1 text-xs text-muted-foreground">همه تنظیمات ساخت و پنل ساب را یک‌جا مشخص کنید.</p></div>
              <Button type="button" size="sm" variant="ghost" onClick={() => setShowOffer(false)}>بستن</Button>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="عنوان نمایشی سرویس"><Input required value={offerForm.title} onChange={(event) => setOfferForm({ ...offerForm, title: event.target.value })} /></Field>
              <Field label="پنل ساخت">
                <select className="h-10 rounded-md border bg-background px-3 text-sm" value={offerForm.panel_key} onChange={(event) => setOfferForm({ ...offerForm, panel_key: event.target.value })}>
                  {panels.map((panel) => <option key={panel.key} value={panel.key}>{panel.title} ({panel.key})</option>)}
                </select>
              </Field>
              <Field label="قیمت همکار (تومان)"><Input dir="ltr" type="number" min={0} value={offerForm.price_toman} onChange={(event) => setOfferForm({ ...offerForm, price_toman: Number(event.target.value) })} /></Field>
              <Field label="حجم ساخت (GB، صفر نامحدود)"><Input dir="ltr" type="number" min={0} value={offerForm.volume_gb} onChange={(event) => setOfferForm({ ...offerForm, volume_gb: Number(event.target.value) })} /></Field>
              <Field label="قفل حجم برای همکار">
                <label className="flex h-10 items-center gap-2 rounded-md border px-3 text-sm"><input className="size-4" type="checkbox" checked={offerForm.lock_volume} onChange={(event) => setOfferForm({ ...offerForm, lock_volume: event.target.checked })} /> حجم این پلن قابل ویرایش نباشد</label>
              </Field>
              <Field label="مدت پیش‌فرض (روز، صفر نامحدود)"><Input dir="ltr" type="number" min={0} value={offerForm.default_duration_days} onChange={(event) => setOfferForm({ ...offerForm, default_duration_days: Number(event.target.value) })} /></Field>
              <Field label="پیشوند و شمارشگر نام"><Input dir="ltr" value={offerForm.name_prefix} onChange={(event) => setOfferForm({ ...offerForm, name_prefix: event.target.value })} /></Field>
              <Field label="HWID پنل (خالی یعنی پیش‌فرض)"><Input dir="ltr" type="number" min={0} value={offerForm.panel_hwid_limit ?? ""} onChange={(event) => setOfferForm({ ...offerForm, panel_hwid_limit: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
              <Field label="محدودیت دستگاه پنل ساب (صفر نامحدود)"><Input dir="ltr" type="number" min={0} value={offerForm.subscription_device_limit} onChange={(event) => setOfferForm({ ...offerForm, subscription_device_limit: Number(event.target.value) })} /></Field>
              <Field label="نام نمایشی داخل برنامه‌ها"><Input value={offerForm.profile_title} onChange={(event) => setOfferForm({ ...offerForm, profile_title: event.target.value })} /></Field>
              <Field label="کانال یا پشتیبانی اختصاصی"><Input dir="ltr" value={offerForm.support_url} onChange={(event) => setOfferForm({ ...offerForm, support_url: event.target.value })} /></Field>
              <Field label="نوع زمان مجاز" wide>
                <div className="flex flex-wrap gap-2">
                  {[["date", "تاریخ‌دار"], ["on_hold", "شروع با اولین اتصال"], ["unlimited", "نامحدود"]].map(([value, label]) => (
                    <button key={value} type="button" onClick={() => toggleMode(value)} className={`rounded-md border px-3 py-2 text-xs ${offerForm.allowed_time_modes.includes(value) ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground"}`}>{label}</button>
                  ))}
                </div>
              </Field>
              <Field label="نوع زمان پیش‌فرض">
                <select className="h-10 rounded-md border bg-background px-3 text-sm" value={offerForm.default_time_mode} onChange={(event) => setOfferForm({ ...offerForm, default_time_mode: event.target.value })}>
                  {offerForm.allowed_time_modes.map((mode) => <option key={mode} value={mode}>{mode}</option>)}
                </select>
              </Field>
              <Field label="قفل نوع تاریخ برای همکار">
                <label className="flex h-10 items-center gap-2 rounded-md border px-3 text-sm"><input className="size-4" type="checkbox" checked={offerForm.lock_time_mode} onChange={(event) => setOfferForm({ ...offerForm, lock_time_mode: event.target.checked })} /> مدل تاریخ قابل تغییر نباشد</label>
              </Field>
              <Field label="قفل مدت سرویس برای همکار">
                <label className="flex h-10 items-center gap-2 rounded-md border px-3 text-sm"><input className="size-4" type="checkbox" checked={offerForm.lock_duration} onChange={(event) => setOfferForm({ ...offerForm, lock_duration: event.target.checked })} /> تعداد روز قابل تغییر نباشد</label>
              </Field>
              <Field label="ویژگی‌های لینک ساب">
                <div className="grid gap-2 rounded-md border p-3 text-xs">
                  <label className="flex items-center gap-2"><input className="size-4" type="checkbox" checked={offerForm.show_header} onChange={(event) => setOfferForm({ ...offerForm, show_header: event.target.checked })} /> نمایش هدر سایت</label>
                  <label className="flex items-center gap-2"><input className="size-4" type="checkbox" checked={offerForm.show_config_preview} onChange={(event) => setOfferForm({ ...offerForm, show_config_preview: event.target.checked })} /> نمایش کانفیگ‌های اشتراک</label>
                  <label className="flex items-center gap-2"><input className="size-4" type="checkbox" checked={offerForm.info_proxies_enabled} onChange={(event) => setOfferForm({ ...offerForm, info_proxies_enabled: event.target.checked })} /> کانفیگ‌های اطلاعاتی</label>
                </div>
              </Field>
            </div>
            <div className="mt-6 flex justify-end gap-2 border-t pt-4">
              <Button type="button" variant="ghost" onClick={() => setShowOffer(false)}>انصراف</Button>
              <Button type="submit" disabled={busy}><PackagePlus className="size-4" /> ذخیره سرویس</Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
