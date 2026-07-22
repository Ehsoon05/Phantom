import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  getBrandedLinks,
  getCryptoSettings,
  getHooshPaySettings,
  getRialSettings,
  getTrialSettings,
  listChannels,
  setBrandedLinks,
  setSubscriptionDeviceLimit,
  setSubscriptionProfileTitle,
  setManualRate,
  setMargin,
  setRateMode,
  setHooshPaySettings,
  setRialSettings,
  setTrialSettings,
  toggleChannel,
  deleteChannel,
  upsertChannel,
} from "@/lib/admin-api";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <p className="text-sm font-semibold">{title}</p>
        {children}
      </CardContent>
    </Card>
  );
}

function CryptoSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["set-crypto"], queryFn: getCryptoSettings });
  const inv = () => qc.invalidateQueries({ queryKey: ["set-crypto"] });
  const [margin, setMar] = useState("");
  const [usdt, setUsdt] = useState("");
  const [ton, setTon] = useState("");
  useEffect(() => { if (data) { setMar(String(data.margin_percent)); setUsdt(String(data.manual_rate_usdt)); setTon(String(data.manual_rate_ton)); } }, [data]);

  const mMode = useMutation({ mutationFn: (m: string) => setRateMode(m), onSuccess: inv });
  const mMargin = useMutation({ mutationFn: () => setMargin(parseFloat(margin)), onSuccess: inv });
  const mUsdt = useMutation({ mutationFn: () => setManualRate("USDT", parseInt(usdt, 10)), onSuccess: inv });
  const mTon = useMutation({ mutationFn: () => setManualRate("TON", parseInt(ton, 10)), onSuccess: inv });

  return (
    <Section title="تنظیمات کریپتو">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">حالت نرخ:</span>
        <Badge>{data?.rate_mode ?? "…"}</Badge>
        <Button size="sm" variant="outline" onClick={() => mMode.mutate(data?.rate_mode === "online" ? "manual" : "online")}>
          تغییر به {data?.rate_mode === "online" ? "دستی" : "آنلاین"}
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <div className="flex gap-1"><Input placeholder="مارجین %" value={margin} onChange={(e) => setMar(e.target.value)} /><Button size="sm" onClick={() => mMargin.mutate()}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="نرخ USDT" value={usdt} onChange={(e) => setUsdt(e.target.value)} /><Button size="sm" onClick={() => mUsdt.mutate()}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="نرخ TON" value={ton} onChange={(e) => setTon(e.target.value)} /><Button size="sm" onClick={() => mTon.mutate()}>ثبت</Button></div>
      </div>
    </Section>
  );
}

function RialSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["set-rial"], queryFn: getRialSettings });
  const inv = () => qc.invalidateQueries({ queryKey: ["set-rial"] });
  const [min, setMin] = useState("");
  const [handle, setHandle] = useState("");
  const [destCard, setDestCard] = useState("");
  const [destHolder, setDestHolder] = useState("");
  const [validMinutes, setValidMinutes] = useState("");
  const [receiptBot, setReceiptBot] = useState("");
  const [receiptAdmins, setReceiptAdmins] = useState("");
  useEffect(() => {
    if (data) {
      setMin(String(data.min_amount_toman));
      setHandle(data.support_handle);
      setDestCard(data.destination_card_number ?? "");
      setDestHolder(data.destination_card_holder ?? "");
      setValidMinutes(String(data.receipt_valid_minutes ?? 120));
      setReceiptBot(data.receipt_bot_username ?? "");
      setReceiptAdmins((data.receipt_admin_ids ?? []).join(","));
    }
  }, [data]);
  const save = useMutation({ mutationFn: (b: Record<string, unknown>) => setRialSettings(b), onSuccess: inv });
  return (
    <Section title="تنظیمات ریالی">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <div className="flex gap-1"><Input placeholder="حداقل مبلغ" value={min} onChange={(e) => setMin(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ min_amount_toman: parseInt(min, 10) })}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="هندل پشتیبانی" dir="ltr" value={handle} onChange={(e) => setHandle(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ support_handle: handle })}>ثبت</Button></div>
        <Button size="sm" variant="outline" onClick={() => save.mutate({ phone_required: !data?.phone_required })}>
          تایید شماره در ربات: {data?.phone_required ? "فعال" : "غیرفعال"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => save.mutate({ source_card_required: !data?.source_card_required })}>
          دریافت کارت مبدا: {data?.source_card_required ? "فعال" : "غیرفعال"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => save.mutate({ payment_mode: data?.payment_mode === "receipt_bot" ? "direct_support" : "receipt_bot" })}>
          روش ریالی: {data?.payment_mode === "receipt_bot" ? "بات رسید" : "پشتیبانی"}
        </Button>
        <div className="flex gap-1"><Input placeholder="شماره کارت مقصد" dir="ltr" value={destCard} onChange={(e) => setDestCard(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ destination_card_number: destCard })}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="صاحب کارت" value={destHolder} onChange={(e) => setDestHolder(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ destination_card_holder: destHolder })}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="اعتبار دقیقه" dir="ltr" value={validMinutes} onChange={(e) => setValidMinutes(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ receipt_valid_minutes: parseInt(validMinutes, 10) })}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="بات رسید" dir="ltr" value={receiptBot} onChange={(e) => setReceiptBot(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ receipt_bot_username: receiptBot })}>ثبت</Button></div>
        <div className="flex gap-1 md:col-span-2"><Input placeholder="ادمین‌های رسید با کاما" dir="ltr" value={receiptAdmins} onChange={(e) => setReceiptAdmins(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ receipt_admin_ids: receiptAdmins.split(/[،,\\s]+/).filter(Boolean).map((v) => parseInt(v, 10)) })}>ثبت</Button></div>
      </div>
    </Section>
  );
}

function HooshPaySection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["set-hooshpay"], queryFn: getHooshPaySettings });
  const inv = () => qc.invalidateQueries({ queryKey: ["set-hooshpay"] });
  const [min, setMin] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [callbackBase, setCallbackBase] = useState("");
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [amountLabel, setAmountLabel] = useState("");
  const [createButton, setCreateButton] = useState("");
  const [payButton, setPayButton] = useState("");
  const [presetAmounts, setPresetAmounts] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  useEffect(() => {
    if (data) {
      setMin(String(data.min_amount_toman));
      setApiBase(data.api_base_url ?? "");
      setCallbackBase(data.callback_base_url ?? "");
      setTitle(data.title ?? "");
      setSubtitle(data.subtitle ?? "");
      setAmountLabel(data.amount_label ?? "");
      setCreateButton(data.create_button ?? "");
      setPayButton(data.pay_button ?? "");
      setPresetAmounts((data.preset_amounts ?? []).join(","));
    }
  }, [data]);
  const save = useMutation({ mutationFn: (b: Record<string, unknown>) => setHooshPaySettings(b), onSuccess: inv });
  return (
    <Section title="تنظیمات درگاه هوش‌پی">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <Button size="sm" variant="outline" onClick={() => save.mutate({ enabled: !data?.enabled })}>
          وضعیت: {data?.enabled ? "فعال" : "غیرفعال"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => save.mutate({ fee_mode: data?.fee_mode === "split" ? "buyer" : "split" })}
        >
          کارمزد: {data?.fee_mode ?? "split"}
        </Button>
        <div className="flex gap-1"><Input placeholder="حداقل مبلغ" value={min} onChange={(e) => setMin(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ min_amount_toman: parseInt(min, 10) })}>ثبت</Button></div>
        <div className="flex gap-1 md:col-span-2"><Input placeholder="تیتر مینی‌اپ" value={title} onChange={(e) => setTitle(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ title })}>ثبت</Button></div>
        <div className="flex gap-1 md:col-span-3"><Input placeholder="توضیح مینی‌اپ" value={subtitle} onChange={(e) => setSubtitle(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ subtitle })}>ثبت</Button></div>
        <div className="flex gap-1 md:col-span-2"><Input placeholder="عنوان فیلد مبلغ" value={amountLabel} onChange={(e) => setAmountLabel(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ amount_label: amountLabel })}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="متن دکمه ساخت" value={createButton} onChange={(e) => setCreateButton(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ create_button: createButton })}>ثبت</Button></div>
        <div className="flex gap-1"><Input placeholder="متن دکمه پرداخت" value={payButton} onChange={(e) => setPayButton(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ pay_button: payButton })}>ثبت</Button></div>
        <div className="flex gap-1 md:col-span-3">
          <Input placeholder="مبلغ‌های آماده مینی‌اپ با کاما، مثال: 100000,200000,500000" dir="ltr" value={presetAmounts} onChange={(e) => setPresetAmounts(e.target.value)} />
          <Button
            size="sm"
            onClick={() =>
              save.mutate({
                preset_amounts: presetAmounts
                  .split(/[،,\\s]+/)
                  .map((value) => parseInt(value, 10))
                  .filter((value) => Number.isFinite(value) && value > 0),
              })
            }
          >
            ثبت
          </Button>
        </div>
        <div className="flex gap-1 md:col-span-2"><Input placeholder="API Base URL" dir="ltr" value={apiBase} onChange={(e) => setApiBase(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ api_base_url: apiBase })}>ثبت</Button></div>
        <div className="flex gap-1 md:col-span-2"><Input placeholder="Callback Base URL" dir="ltr" value={callbackBase} onChange={(e) => setCallbackBase(e.target.value)} /><Button size="sm" onClick={() => save.mutate({ callback_base_url: callbackBase })}>ثبت</Button></div>
        <div className="flex gap-1 md:col-span-2">
          <Input placeholder={data?.api_key_configured ? "API Key تنظیم شده؛ برای تغییر مقدار جدید وارد کنید" : "API Key"} dir="ltr" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          <Button size="sm" disabled={!apiKey.trim()} onClick={() => { save.mutate({ api_key: apiKey }); setApiKey(""); }}>ثبت</Button>
        </div>
        <div className="flex gap-1 md:col-span-2">
          <Input placeholder={data?.api_secret_configured ? "API Secret تنظیم شده؛ برای تغییر مقدار جدید وارد کنید" : "API Secret"} dir="ltr" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} />
          <Button size="sm" disabled={!apiSecret.trim()} onClick={() => { save.mutate({ api_secret: apiSecret }); setApiSecret(""); }}>ثبت</Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        حالت پیش‌فرض کارمزد split است. Secret در پنل نمایش داده نمی‌شود و فقط وضعیت تنظیم بودن آن دیده می‌شود.
      </p>
    </Section>
  );
}

function TrialSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["set-trial"], queryFn: getTrialSettings });
  const inv = () => qc.invalidateQueries({ queryKey: ["set-trial"] });
  const [vol, setVol] = useState("");
  const [dur, setDur] = useState("");
  const [panelKey, setPanelKey] = useState("");
  const [timeMode, setTimeMode] = useState("date");
  useEffect(() => {
    if (data) {
      setVol(String(data.volume_mb));
      setDur(String(data.duration_hours));
      setPanelKey(data.panel_key || "");
      setTimeMode(data.time_mode || "date");
    }
  }, [data]);
  const save = useMutation({ mutationFn: (b: Record<string, unknown>) => setTrialSettings(b), onSuccess: inv });
  return (
    <Section title="تنظیمات تست رایگان">
      <div className="grid gap-2 md:grid-cols-3">
        <Button size="sm" variant="outline" onClick={() => save.mutate({ enabled: !data?.enabled })}>وضعیت: {data?.enabled ? "فعال" : "غیرفعال"}</Button>
        <label className="space-y-1 text-xs">
          <span className="text-muted-foreground">پنل ساخت تست</span>
          <select
            className="min-h-9 w-full rounded-md border bg-transparent px-3 text-sm"
            value={panelKey}
            onChange={(e) => {
              setPanelKey(e.target.value);
              if (e.target.value) save.mutate({ panel_key: e.target.value });
            }}
          >
            <option value="">انتخاب پنل</option>
            {data?.panels?.map((panel) => (
              <option key={panel.key} value={panel.key}>{panel.title} ({panel.key})</option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs">
          <span className="text-muted-foreground">نوع زمان تست</span>
          <select
            className="min-h-9 w-full rounded-md border bg-transparent px-3 text-sm"
            value={timeMode}
            onChange={(e) => {
              setTimeMode(e.target.value);
              save.mutate({ time_mode: e.target.value });
            }}
          >
            <option value="date">تاریخ‌دار از زمان ساخت</option>
            <option value="on_hold">شروع از اولین اتصال</option>
            <option value="unlimited">بدون محدودیت زمان</option>
          </select>
        </label>
        <div className="flex gap-1">
          <Input placeholder="حجم MB" inputMode="numeric" value={vol} onChange={(e) => setVol(e.target.value)} />
          <Button size="sm" onClick={() => save.mutate({ volume_mb: parseInt(vol, 10) })}>ثبت</Button>
        </div>
        <div className="flex gap-1">
          <Input placeholder="مدت (ساعت)" inputMode="numeric" value={dur} onChange={(e) => setDur(e.target.value)} />
          <Button size="sm" onClick={() => save.mutate({ duration_hours: parseInt(dur, 10) })}>ثبت</Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        برای تست‌های تاریخ‌دار، کانفیگ از لحظه ساخت فعال می‌شود. برای حالت شروع از اولین اتصال، زمان از اولین استفاده محاسبه می‌شود.
      </p>
    </Section>
  );
}

function BrandedSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["set-branded"], queryFn: getBrandedLinks });
  const [title, setTitle] = useState("");
  const [deviceLimit, setDeviceLimit] = useState("");
  useEffect(() => {
    if (data) {
      setTitle(data.subscription_profile_title ?? "");
      setDeviceLimit(String(data.subscription_device_limit ?? 0));
    }
  }, [data]);
  const save = useMutation({ mutationFn: (e: boolean) => setBrandedLinks(e), onSuccess: () => qc.invalidateQueries({ queryKey: ["set-branded"] }) });
  const saveTitle = useMutation({
    mutationFn: () => setSubscriptionProfileTitle(title),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["set-branded"] }),
  });
  const saveDeviceLimit = useMutation({
    mutationFn: () => setSubscriptionDeviceLimit(Math.max(0, parseInt(deviceLimit || "0", 10) || 0)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["set-branded"] }),
  });
  return (
    <Section title="لینک‌های اختصاصی">
      <div className="grid gap-2 md:grid-cols-[auto_minmax(0,1fr)_auto]">
        <Button size="sm" variant="outline" onClick={() => save.mutate(!data?.enabled)}>وضعیت: {data?.enabled ? "فعال" : "غیرفعال"}</Button>
        <Input
          placeholder="نام نمایشی سابسکریپشن داخل برنامه‌ها"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <Button size="sm" onClick={() => saveTitle.mutate()} disabled={saveTitle.isPending}>ثبت نام</Button>
      </div>
      <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
        <Input
          type="number"
          min={0}
          placeholder="محدودیت کاربر/دستگاه لینک‌های ساب؛ 0 یعنی نامحدود"
          value={deviceLimit}
          onChange={(e) => setDeviceLimit(e.target.value)}
        />
        <Button size="sm" onClick={() => saveDeviceLimit.mutate()} disabled={saveDeviceLimit.isPending}>ثبت محدودیت</Button>
      </div>
      <p className="text-xs text-muted-foreground">
        این نام و محدودیت روی خروجی خام لینک‌های ساب اعمال می‌شود. صفر یعنی نامحدود باشد.
      </p>
    </Section>
  );
}

function ChannelsSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["set-channels"], queryFn: listChannels });
  const inv = () => qc.invalidateQueries({ queryKey: ["set-channels"] });
  const [f, setF] = useState({ chat_id: "", title: "", join_url: "" });
  const add = useMutation({ mutationFn: () => upsertChannel(f), onSuccess: () => { setF({ chat_id: "", title: "", join_url: "" }); inv(); } });
  const tog = useMutation({ mutationFn: (id: number) => toggleChannel(id), onSuccess: inv });
  const del = useMutation({ mutationFn: (id: number) => deleteChannel(id), onSuccess: inv });
  return (
    <Section title="کانال‌های اجباری">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Input placeholder="chat_id" dir="ltr" value={f.chat_id} onChange={(e) => setF({ ...f, chat_id: e.target.value })} />
        <Input placeholder="عنوان" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
        <Input placeholder="لینک عضویت" dir="ltr" value={f.join_url} onChange={(e) => setF({ ...f, join_url: e.target.value })} />
        <Button size="sm" disabled={!f.chat_id || !f.title || !f.join_url} onClick={() => add.mutate()}>افزودن</Button>
      </div>
      <div className="space-y-1">
        {data?.map((c) => (
          <div key={c.id} className="flex items-center justify-between text-sm">
            <span>{c.title} <span className="text-xs text-muted-foreground" dir="ltr">{c.chat_id}</span> {!c.is_active && <Badge variant="destructive">خاموش</Badge>}</span>
            <span className="flex gap-1">
              <Button size="sm" variant="secondary" onClick={() => tog.mutate(c.id)}>{c.is_active ? "خاموش" : "روشن"}</Button>
              <Button size="sm" variant="destructive" onClick={() => del.mutate(c.id)}>حذف</Button>
            </span>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">تنظیمات</h1>
      <CryptoSection />
      <RialSection />
      <HooshPaySection />
      <TrialSection />
      <BrandedSection />
      <ChannelsSection />
    </div>
  );
}
