import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";

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
  deleteInventoryConfig,
  deletePlan,
  getInventoryStock,
  listCategories,
  listInventoryConfigs,
  listProvisionPanels,
  listPlans,
  replaceInventoryConfig,
  setPlanPrice,
  type Plan,
  updatePlan,
  updateInventoryConfigDeviceLimit,
  upsertCategory,
  upsertPlan,
} from "@/lib/admin-api";

type ProvisionForm = {
  title: string;
  emoji: string;
  style: string;
  category_key: string;
  price: string;
  volume_gb: string;
  display_order: string;
  provision_mode: string;
  provision_panel_key: string;
  name_prefix: string;
  duration_days: string;
  provision_time_mode: string;
  provision_duration_days: string;
  provision_volume_gb: string;
  subscription_device_limit: string;
  show_subscription_configs: boolean;
  renew_enabled: boolean;
};

function provisionFormFromPlan(plan: Plan): ProvisionForm {
  const legacyUnlimited = plan.provision_time_mode === "unlimited";
  return {
    title: plan.title ?? "",
    emoji: plan.emoji ?? "",
    style: plan.style ?? "success",
    category_key: plan.category_key || "default",
    price: plan.price != null ? String(plan.price) : "",
    volume_gb: String(plan.volume_gb ?? 0),
    display_order: String(plan.display_order ?? 0),
    provision_mode: plan.provision_mode || "inventory_then_panel",
    provision_panel_key: plan.provision_panel_key ?? "",
    name_prefix: plan.name_prefix ?? `PhantomHubs_${plan.category_key}_${plan.volume_gb}GB`,
    duration_days: legacyUnlimited ? "0" : String(plan.duration_days ?? 30),
    provision_time_mode: plan.provision_time_mode === "date" ? "date" : "on_hold",
    provision_duration_days: plan.provision_duration_days != null ? String(plan.provision_duration_days) : legacyUnlimited ? "0" : "",
    provision_volume_gb: plan.provision_volume_gb != null ? String(plan.provision_volume_gb) : "",
    subscription_device_limit: String(plan.subscription_device_limit ?? 0),
    show_subscription_configs: Boolean(plan.show_subscription_configs),
    renew_enabled: Boolean(plan.renew_enabled),
  };
}

function PlansTab() {
  const qc = useQueryClient();
  const { data: plans, isLoading } = useQuery({ queryKey: ["admin-plans"], queryFn: listPlans });
  const { data: categories } = useQuery({ queryKey: ["admin-categories"], queryFn: listCategories });
  const { data: panels } = useQuery({ queryKey: ["provision-panels"], queryFn: listProvisionPanels });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-plans"] });

  const [form, setForm] = useState({ volume_gb: "", title: "", price: "", category_key: "default" });
  const [provisionPlanId, setProvisionPlanId] = useState<number | null>(null);
  const [provisionForm, setProvisionForm] = useState<ProvisionForm | null>(null);
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
    onSuccess: () => {
      setProvisionPlanId(null);
      setProvisionForm(null);
      invalidate();
    },
  });
  const toggle = useMutation({
    mutationFn: (p: { id: number; is_active: boolean }) => updatePlan(p.id, { is_active: !p.is_active }),
    onSuccess: invalidate,
  });
  const provision = useMutation({
    mutationFn: (input: {
      id: number;
      provision_mode: string;
      provision_panel_key: string | null;
      provision_enabled: boolean;
      renew_enabled: boolean;
      title: string;
      emoji: string | null;
      style: string | null;
      category_key: string;
      price: number | null;
      volume_gb: number;
      display_order: number;
      duration_days: number;
      provision_volume_gb: number | null;
      provision_duration_days: number | null;
      provision_time_mode: string;
      subscription_device_limit: number;
      show_subscription_configs: boolean;
      name_prefix: string | null;
    }) => updatePlan(input.id, input),
    onSuccess: invalidate,
  });
  const remove = useMutation({ mutationFn: (id: number) => deletePlan(id), onSuccess: invalidate });

  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="grid grid-cols-2 gap-2 p-4 md:grid-cols-5">
          <Input placeholder="حجم (GB) یا 0 برای نامحدود" inputMode="numeric" value={form.volume_gb} onChange={(e) => setForm({ ...form, volume_gb: e.target.value })} />
          <Input placeholder="عنوان" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <Input placeholder="قیمت (تومان)" inputMode="numeric" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
          <select
            className="min-h-9 rounded-md border bg-transparent px-3 text-sm"
            value={form.category_key}
            onChange={(e) => setForm({ ...form, category_key: e.target.value })}
          >
            <option value="default">پیش‌فرض</option>
            {categories?.filter((category) => category.key !== "default").map((category) => (
              <option key={category.id} value={category.key}>{category.emoji} {category.title}</option>
            ))}
          </select>
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
                <th className="pb-2">قیمت</th><th className="pb-2">تامین</th><th className="pb-2">موجودی</th><th className="pb-2">وضعیت</th><th className="pb-2">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {plans?.map((p) => (
                <Fragment key={p.id}>
                <tr className="border-b last:border-0">
                  <td className="py-2">{p.emoji} {p.title}</td>
                  <td className="py-2 text-muted-foreground">{p.category_key}</td>
                  <td className="py-2">{p.volume_gb > 0 ? `${p.volume_gb} GB` : "نامحدود"}</td>
                  <td className="py-2">{p.price != null ? formatToman(p.price) : "—"}</td>
                  <td className="py-2 text-xs">
                    {p.provision_enabled ? `${p.provision_mode} · ${p.provision_panel_key ?? "دسته"}` : "انبار"}
                  </td>
                  <td className="py-2"><Badge variant={(p.stock ?? 0) <= 3 ? "destructive" : "secondary"}>{p.stock ?? 0}</Badge></td>
                  <td className="py-2">{p.is_active ? "✅" : "⛔"}</td>
                  <td className="flex flex-wrap gap-1 py-2">
                    <Button size="sm" variant="outline" onClick={() => { const v = prompt("قیمت جدید:", String(p.price ?? "")); const n = parseInt(v ?? "", 10); if (!Number.isNaN(n)) price.mutate({ id: p.id, p: n }); }}>قیمت</Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (provisionPlanId === p.id) {
                          setProvisionPlanId(null);
                          setProvisionForm(null);
                        } else {
                          setProvisionPlanId(p.id);
                          setProvisionForm(provisionFormFromPlan(p));
                        }
                      }}
                    >
                      ویرایش کامل
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => toggle.mutate({ id: p.id, is_active: p.is_active })}>{p.is_active ? "غیرفعال" : "فعال"}</Button>
                    <Button size="sm" variant="destructive" onClick={() => { if (confirm("حذف پلن؟")) remove.mutate(p.id); }}>حذف</Button>
                  </td>
                </tr>
                {provisionPlanId === p.id && provisionForm && (
                  <tr className="border-b bg-muted/30">
                    <td colSpan={8} className="py-3">
                      <div className="grid gap-3 rounded-lg border bg-background p-3 md:grid-cols-4">
                        <div className="space-y-1 md:col-span-4">
                          <p className="text-sm font-semibold">ویرایش کامل پلن و تنظیمات ساخت</p>
                          <p className="text-xs text-muted-foreground">
                            اطلاعات نمایشی برای فروشگاه است؛ فیلدهای ساخت مشخص می‌کنند اگر پلن از پنل ساخته شود با چه نام، حجم، زمان و محدودیتی ساخته شود.
                          </p>
                        </div>
                        <label className="space-y-1 text-xs md:col-span-2">
                          <span className="text-muted-foreground">اسم نمایشی پلن</span>
                          <Input
                            value={provisionForm.title}
                            onChange={(e) => setProvisionForm({ ...provisionForm, title: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">ایموجی پلن</span>
                          <Input
                            value={provisionForm.emoji}
                            onChange={(e) => setProvisionForm({ ...provisionForm, emoji: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">رنگ/استایل دکمه</span>
                          <select
                            className="min-h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                            value={provisionForm.style}
                            onChange={(e) => setProvisionForm({ ...provisionForm, style: e.target.value })}
                          >
                            <option value="primary">Primary</option>
                            <option value="success">Success</option>
                            <option value="danger">Danger</option>
                            <option value="secondary">Secondary</option>
                            <option value="outline">Outline</option>
                          </select>
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">دسته سرویس</span>
                          <select
                            className="min-h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                            value={provisionForm.category_key}
                            onChange={(e) => setProvisionForm({ ...provisionForm, category_key: e.target.value })}
                          >
                            <option value="default">پیش‌فرض</option>
                            {categories?.filter((category) => category.key !== "default").map((category) => (
                              <option key={category.id} value={category.key}>{category.emoji} {category.title}</option>
                            ))}
                          </select>
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">قیمت فروش (تومان)</span>
                          <Input
                            inputMode="numeric"
                            value={provisionForm.price}
                            onChange={(e) => setProvisionForm({ ...provisionForm, price: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">حجم نمایشی/فروش (GB)</span>
                          <Input
                            inputMode="numeric"
                            placeholder="0 یعنی نامحدود"
                            value={provisionForm.volume_gb}
                            onChange={(e) => setProvisionForm({ ...provisionForm, volume_gb: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">ترتیب نمایش</span>
                          <Input
                            inputMode="numeric"
                            value={provisionForm.display_order}
                            onChange={(e) => setProvisionForm({ ...provisionForm, display_order: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">حالت تامین</span>
                          <select
                            className="min-h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                            value={provisionForm.provision_mode}
                            onChange={(e) => setProvisionForm({ ...provisionForm, provision_mode: e.target.value })}
                          >
                            <option value="inventory">فقط انبار</option>
                            <option value="inventory_then_panel">اول انبار، بعد پنل</option>
                            <option value="panel_only">فقط پنل</option>
                          </select>
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">پنل ساخت</span>
                          <select
                            className="min-h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                            value={provisionForm.provision_panel_key}
                            onChange={(e) => setProvisionForm({ ...provisionForm, provision_panel_key: e.target.value })}
                          >
                            <option value="">پنل دسته/پیش‌فرض</option>
                            {panels?.map((panel) => (
                              <option key={panel.key} value={panel.key}>{panel.title} ({panel.key})</option>
                            ))}
                          </select>
                        </label>
                        <label className="space-y-1 text-xs md:col-span-2">
                          <span className="text-muted-foreground">اسم ساخت در پنل / شروع شمارنده</span>
                          <Input
                            dir="ltr"
                            placeholder="مثال: PhantomExpress10GB-VIP1"
                            value={provisionForm.name_prefix}
                            onChange={(e) => setProvisionForm({ ...provisionForm, name_prefix: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">مدت سرویس به روز</span>
                          <Input
                            inputMode="numeric"
                            placeholder="0 یعنی نامحدود"
                            value={provisionForm.duration_days}
                            onChange={(e) => setProvisionForm({ ...provisionForm, duration_days: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">نوع زمان ساخت</span>
                          <select
                            className="min-h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                            value={provisionForm.provision_time_mode}
                            onChange={(e) => setProvisionForm({ ...provisionForm, provision_time_mode: e.target.value })}
                          >
                            <option value="on_hold">On Hold</option>
                            <option value="date">تاریخ‌دار</option>
                          </select>
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">مدت واقعی ساخت/تمدید</span>
                          <Input
                            inputMode="numeric"
                            placeholder="خالی یعنی مدت سرویس، 0 یعنی نامحدود"
                            value={provisionForm.provision_duration_days}
                            onChange={(e) => setProvisionForm({ ...provisionForm, provision_duration_days: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">حجم واقعی در پنل (GB)</span>
                          <Input
                            inputMode="numeric"
                            placeholder="خالی یعنی حجم نمایشی"
                            value={provisionForm.provision_volume_gb}
                            onChange={(e) => setProvisionForm({ ...provisionForm, provision_volume_gb: e.target.value })}
                          />
                        </label>
                        <label className="space-y-1 text-xs">
                          <span className="text-muted-foreground">محدودیت کاربر/دستگاه</span>
                          <Input
                            inputMode="numeric"
                            value={provisionForm.subscription_device_limit}
                            onChange={(e) => setProvisionForm({ ...provisionForm, subscription_device_limit: e.target.value })}
                          />
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={provisionForm.show_subscription_configs}
                            onChange={(e) => setProvisionForm({ ...provisionForm, show_subscription_configs: e.target.checked })}
                          />
                          نمایش کانفیگ‌ها در صفحه وب
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={provisionForm.renew_enabled}
                            onChange={(e) => setProvisionForm({ ...provisionForm, renew_enabled: e.target.checked })}
                          />
                          تمدید فعال باشد
                        </label>
                        <div className="flex items-end gap-2 md:col-span-2">
                          <Button
                            disabled={provision.isPending}
                            onClick={() => {
                              const duration = parseInt(provisionForm.duration_days, 10);
                              const volumeGb = parseInt(provisionForm.volume_gb, 10);
                              const displayOrder = parseInt(provisionForm.display_order, 10);
                              const priceValue = provisionForm.price.trim() ? parseInt(provisionForm.price, 10) : null;
                              const provisionDuration = provisionForm.provision_duration_days.trim()
                                ? parseInt(provisionForm.provision_duration_days, 10)
                                : null;
                              const actualVolume = provisionForm.provision_volume_gb.trim()
                                ? parseInt(provisionForm.provision_volume_gb, 10)
                                : null;
                              const deviceLimit = parseInt(provisionForm.subscription_device_limit, 10);
                              if (
                                !provisionForm.title.trim() ||
                                Number.isNaN(volumeGb) ||
                                volumeGb < 0 ||
                                Number.isNaN(displayOrder) ||
                                (priceValue != null && (Number.isNaN(priceValue) || priceValue < 0)) ||
                                Number.isNaN(duration) ||
                                duration < 0 ||
                                (provisionDuration != null && (Number.isNaN(provisionDuration) || provisionDuration < 0)) ||
                                (actualVolume != null && (Number.isNaN(actualVolume) || actualVolume < 0)) ||
                                Number.isNaN(deviceLimit) ||
                                deviceLimit < 0
                              ) {
                                alert("مقادیر عددی را درست وارد کنید.");
                                return;
                              }
                              provision.mutate({
                                id: p.id,
                                title: provisionForm.title.trim(),
                                emoji: provisionForm.emoji.trim() || null,
                                style: provisionForm.style || null,
                                category_key: provisionForm.category_key || "default",
                                price: priceValue,
                                volume_gb: volumeGb,
                                display_order: displayOrder,
                                provision_mode: provisionForm.provision_mode,
                                provision_panel_key: provisionForm.provision_panel_key || null,
                                provision_enabled: provisionForm.provision_mode !== "inventory",
                                renew_enabled: provisionForm.renew_enabled,
                                duration_days: duration,
                                provision_volume_gb: actualVolume,
                                provision_duration_days: provisionDuration,
                                provision_time_mode: provisionForm.provision_time_mode,
                                subscription_device_limit: deviceLimit,
                                show_subscription_configs: provisionForm.show_subscription_configs,
                                name_prefix: provisionForm.name_prefix.trim() || null,
                              });
                            }}
                          >
                            ذخیره تنظیمات تامین
                          </Button>
                          <Button type="button" variant="ghost" onClick={() => { setProvisionPlanId(null); setProvisionForm(null); }}>
                            بستن
                          </Button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
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
  const { data: plans } = useQuery({ queryKey: ["admin-plans"], queryFn: listPlans });
  const { data: categories } = useQuery({ queryKey: ["admin-categories"], queryFn: listCategories });
  const [planId, setPlanId] = useState("");
  const [links, setLinks] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterVolume, setFilterVolume] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [replacementLink, setReplacementLink] = useState("");
  const [limitEditingId, setLimitEditingId] = useState<number | null>(null);
  const [deviceLimitValue, setDeviceLimitValue] = useState("");
  const parsedFilterVolume = parseInt(filterVolume, 10);
  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ["admin-inventory-configs", filterCategory, filterVolume, search],
    queryFn: () =>
      listInventoryConfigs(
        filterCategory || undefined,
        Number.isNaN(parsedFilterVolume) ? undefined : parsedFilterVolume,
        search || undefined,
      ),
  });
  const add = useMutation({
    mutationFn: () => {
      const selectedPlan = plans?.find((plan) => plan.id === parseInt(planId, 10));
      if (!selectedPlan) throw new Error("سرویس انتخاب‌شده معتبر نیست.");
      return addConfigs(
        selectedPlan.id,
        selectedPlan.volume_gb,
        selectedPlan.category_key,
        links.split("\n").map((l) => l.trim()).filter(Boolean),
      );
    },
    onSuccess: (r) => {
      alert(`${r.added} کانفیگ اضافه شد`);
      setLinks("");
      qc.invalidateQueries({ queryKey: ["admin-stock"] });
      qc.invalidateQueries({ queryKey: ["admin-inventory-configs"] });
    },
  });
  const replace = useMutation({
    mutationFn: ({ id, subLink }: { id: number; subLink: string }) =>
      replaceInventoryConfig(id, subLink),
    onSuccess: () => {
      setEditingId(null);
      setReplacementLink("");
      qc.invalidateQueries({ queryKey: ["admin-inventory-configs"] });
      alert("لینک جایگزین و پنل اشتراک دوباره همگام شد.");
    },
    onError: (error) => alert(error instanceof Error ? error.message : "جایگزینی لینک انجام نشد."),
  });
  const updateDeviceLimit = useMutation({
    mutationFn: ({ id, limit }: { id: number; limit: number }) =>
      updateInventoryConfigDeviceLimit(id, limit),
    onSuccess: () => {
      setLimitEditingId(null);
      setDeviceLimitValue("");
      qc.invalidateQueries({ queryKey: ["admin-inventory-configs"] });
      alert("محدودیت کاربر لینک ذخیره و پنل اشتراک همگام شد.");
    },
    onError: (error) => alert(error instanceof Error ? error.message : "محدودیت کاربر ذخیره نشد."),
  });
  const removeConfig = useMutation({
    mutationFn: (id: number) => deleteInventoryConfig(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-stock"] });
      qc.invalidateQueries({ queryKey: ["admin-inventory-configs"] });
      alert("لینک از انبار حذف شد.");
    },
    onError: (error) => alert(error instanceof Error ? error.message : "حذف لینک انجام نشد."),
  });
  const copyLink = async (subLink: string) => {
    try {
      await navigator.clipboard.writeText(subLink);
      alert("لینک کپی شد.");
    } catch {
      window.prompt("برای کپی لینک:", subLink);
    }
  };

  return (
    <div className="space-y-4">
      <Card><CardContent className="space-y-2 p-4">
        <p className="text-sm font-semibold">افزودن کانفیگ</p>
        <div>
          <select
            className="min-h-10 w-full rounded-md border bg-transparent px-3 text-sm"
            value={planId}
            onChange={(e) => setPlanId(e.target.value)}
          >
            <option value="">انتخاب سرویس</option>
            {plans?.filter((plan) => plan.is_active).map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.emoji} {plan.title} - {plan.volume_gb > 0 ? `${plan.volume_gb} GB` : "نامحدود"} ({plan.category_key})
              </option>
            ))}
          </select>
        </div>
        <textarea className="min-h-28 w-full rounded-md border bg-transparent p-2 text-sm" dir="ltr" placeholder="هر خط یک لینک ساب" value={links} onChange={(e) => setLinks(e.target.value)} />
        <Button disabled={!planId || !links.trim() || add.isPending} onClick={() => add.mutate()}>{add.isPending ? "در حال افزودن…" : "افزودن"}</Button>
      </CardContent></Card>
      {isLoading ? <Skeleton className="h-32 w-full rounded-xl" /> : (
        <Card><CardContent className="overflow-x-auto p-4">
          <table className="w-full text-sm"><thead><tr className="border-b text-right text-xs text-muted-foreground">
            <th className="pb-2">پلن</th><th className="pb-2">دسته</th><th className="pb-2">حجم</th><th className="pb-2">موجودی</th></tr></thead>
            <tbody>{stock?.map((s) => (
              <tr key={s.plan_id} className="border-b last:border-0">
                <td className="py-2">{s.title}</td><td className="py-2 text-muted-foreground">{s.category_key}</td>
                <td className="py-2">{s.volume_gb > 0 ? `${s.volume_gb} GB` : "نامحدود"}</td><td className="py-2"><Badge variant={s.available <= 3 ? "destructive" : "secondary"}>{s.available}</Badge></td>
              </tr>))}</tbody></table>
        </CardContent></Card>
      )}
      <Card>
        <CardContent className="space-y-4 p-4">
          <div>
            <p className="text-sm font-semibold">اصلاح لینک‌های موجودی</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              جایگزینی، دسته و حجم و تعداد موجودی را تغییر نمی‌دهد و همان لینک عمومی را دوباره همگام می‌کند.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <select
              className="min-h-10 rounded-md border bg-transparent px-3 text-sm"
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
            >
              <option value="">همه دسته‌ها</option>
              <option value="default">پیش‌فرض</option>
              {categories?.filter((item) => item.key !== "default").map((item) => (
                <option key={item.id} value={item.key}>{item.emoji} {item.title}</option>
              ))}
            </select>
            <Input
              placeholder="فیلتر حجم (GB)"
              inputMode="numeric"
              value={filterVolume}
              onChange={(e) => setFilterVolume(e.target.value)}
            />
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => { e.preventDefault(); setSearch(searchInput.trim()); }}
          >
            <Input
              placeholder="جستجوی لینک یا نام ساب…"
              dir="ltr"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <Button type="submit" variant="secondary">جستجو</Button>
            {search && (
              <Button type="button" variant="ghost" onClick={() => { setSearchInput(""); setSearch(""); }}>
                پاک‌سازی
              </Button>
            )}
          </form>
          {configsLoading ? <Skeleton className="h-28 w-full rounded-lg" /> : (
            <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-sm">
                <thead>
                  <tr className="border-b text-right text-xs text-muted-foreground">
                    <th className="pb-2">شناسه</th>
                    <th className="pb-2">نام ساب</th>
                    <th className="pb-2">دسته</th>
                    <th className="pb-2">حجم</th>
                    <th className="pb-2">محدودیت کاربر</th>
                    <th className="pb-2">لینک فعلی</th>
                    <th className="pb-2">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {configs?.map((config) => (
                    <tr key={config.id} className="border-b align-top last:border-0">
                      <td className="py-3">{config.id}</td>
                      <td className="py-3 font-medium">{config.name || "—"}</td>
                      <td className="py-3">{config.category_key}</td>
                      <td className="py-3">{config.volume_gb > 0 ? `${config.volume_gb} GB` : "نامحدود"}</td>
                      <td className="py-3">
                        {limitEditingId === config.id ? (
                          <div className="flex min-w-36 gap-1">
                            <Input
                              inputMode="numeric"
                              className="w-24"
                              value={deviceLimitValue}
                              onChange={(e) => setDeviceLimitValue(e.target.value)}
                              placeholder="0"
                            />
                            <Button
                              size="sm"
                              disabled={updateDeviceLimit.isPending || Number.isNaN(parseInt(deviceLimitValue, 10)) || parseInt(deviceLimitValue, 10) < 0}
                              onClick={() => updateDeviceLimit.mutate({ id: config.id, limit: parseInt(deviceLimitValue, 10) })}
                            >
                              ثبت
                            </Button>
                          </div>
                        ) : (
                          config.subscription_device_limit == null
                            ? "ارث‌بری"
                            : config.subscription_device_limit === 0
                              ? "نامحدود"
                              : `${config.subscription_device_limit} کاربر`
                        )}
                      </td>
                      <td className="max-w-80 py-3">
                        {editingId === config.id ? (
                          <Input
                            type="url"
                            dir="ltr"
                            className="min-w-80 text-left"
                            value={replacementLink}
                            onChange={(e) => setReplacementLink(e.target.value)}
                            placeholder="https://..."
                          />
                        ) : (
                          <span className="block truncate text-xs text-muted-foreground" dir="ltr" title={config.sub_link}>
                            {config.sub_link}
                          </span>
                        )}
                      </td>
                      <td className="py-2">
                        {editingId === config.id ? (
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              disabled={!replacementLink.trim() || replace.isPending}
                              onClick={() => replace.mutate({ id: config.id, subLink: replacementLink.trim() })}
                            >
                              ذخیره
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => { setEditingId(null); setReplacementLink(""); }}>
                              لغو
                            </Button>
                          </div>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => copyLink(config.sub_link)}
                            >
                              کپی لینک
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => { setEditingId(config.id); setReplacementLink(config.sub_link); }}
                            >
                              جایگزینی لینک
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setLimitEditingId(config.id);
                                setDeviceLimitValue(String(config.subscription_device_limit ?? 0));
                              }}
                            >
                              محدودیت کاربر
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={removeConfig.isPending}
                              onClick={() => {
                                if (confirm("این لینک از انبار حذف شود؟")) removeConfig.mutate(config.id);
                              }}
                            >
                              حذف از انبار
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!configs?.length && (
                <p className="py-8 text-center text-sm text-muted-foreground">لینک موجودی پیدا نشد.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function CatalogPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-bold sm:text-xl">محصولات و انبار</h1>
      <Tabs defaultValue="plans">
        <TabsList className="w-full overflow-x-auto">
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
