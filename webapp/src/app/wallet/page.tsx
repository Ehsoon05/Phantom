"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import QRCode from "react-qr-code";

import { AuthGate } from "@/components/auth-gate";
import CountUp from "@/components/reactbits/CountUp";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ApiError,
  applyCoupon,
  cancelCryptoInvoice,
  createCryptoInvoice,
  createHooshPayInvoice,
  createRialRequest,
  formatToman,
  getCryptoInvoice,
  getCryptoInvoices,
  getHooshPayInvoices,
  getMe,
  getPaymentMethods,
  getRialRequests,
  getTransactions,
  verifyHooshPayInvoice,
  tonTransferLink,
  type AppliedCoupon,
  type CryptoInvoice,
  type HooshPayInvoice,
  type RialRequest,
} from "@/lib/api";
import { formatTehranDateTime, formatTehranTime } from "@/lib/date";
import { getWebApp } from "@/lib/telegram";

// Persian digits -> latin, for amount inputs typed with a Persian keyboard.
function parseAmount(value: string): number {
  const normalized = value.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
  return parseInt(normalized.replace(/[^0-9]/g, ""), 10) || 0;
}

const STATUS_LABELS: Record<string, { label: string; tone: "default" | "secondary" | "destructive" }> = {
  pending: { label: "در انتظار پرداخت", tone: "secondary" },
  paid: { label: "تراکنش دیده شد", tone: "default" },
  confirmed: { label: "در حال تایید", tone: "default" },
  credited: { label: "شارژ شد ✅", tone: "default" },
  expired: { label: "منقضی شد", tone: "destructive" },
  underpaid: { label: "مبلغ ناقص", tone: "destructive" },
  error: { label: "خطا", tone: "destructive" },
};

function cryptoAssetLabel(value?: string | null) {
  return value?.toUpperCase() === "TON" ? "گرام(تون)" : value ?? "";
}

function dateMs(value?: string | null): number | null {
  if (!value) return null;
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const parsed = new Date(normalized).getTime();
  return Number.isNaN(parsed) ? null : parsed;
}

function Countdown({ expiresAt }: { expiresAt: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const remaining = Math.max(0, new Date(expiresAt + "Z").getTime() - now);
  const minutes = Math.floor(remaining / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1000);
  return (
    <span dir="ltr" className="font-mono tabular-nums">
      {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
    </span>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="w-full space-y-1 rounded-lg bg-muted p-3 text-right"
      onClick={() => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      <p className="text-xs text-muted-foreground">
        {label} {copied && <span className="text-primary">(کپی شد ✓)</span>}
      </p>
      <p className="break-all text-xs" dir="ltr">
        {value}
      </p>
    </button>
  );
}

function formatCardNumber(value: string) {
  return value.replace(/\D/g, "").replace(/(.{4})/g, "$1 ").trim();
}

function DestinationCardBox({
  card,
  holder,
}: {
  card: string;
  holder?: string | null;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="w-full rounded-xl border border-primary/35 bg-primary/5 p-4 text-center"
      onClick={() => {
        navigator.clipboard.writeText(card);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      <p className="text-xs font-medium text-muted-foreground">
        برای کپی شماره کارت، روی این بخش لمس کنید
      </p>
      <p className="mt-2 font-mono text-xl font-bold tracking-wide text-primary tabular-nums" dir="ltr">
        {formatCardNumber(card)}
      </p>
      {holder && <p className="mt-2 text-xs text-muted-foreground">{holder}</p>}
      {copied && <p className="mt-2 text-xs font-bold text-primary">کپی شد ✓</p>}
    </button>
  );
}

function InvoiceView({ invoice, onClose }: { invoice: CryptoInvoice; onClose: () => void }) {
  const queryClient = useQueryClient();
  // Live status: poll while the invoice is still settling.
  const { data: live } = useQuery({
    queryKey: ["crypto-invoice", invoice.id],
    queryFn: () => getCryptoInvoice(invoice.id),
    initialData: invoice,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "paid" || status === "confirmed" ? 4000 : false;
    },
  });
  const status = STATUS_LABELS[live.status] ?? STATUS_LABELS.pending;
  const settled = live.status === "credited";
  const tonUrl = tonTransferLink(live);

  const cancel = useMutation({
    mutationFn: () => cancelCryptoInvoice(live.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crypto-invoices"] });
      onClose();
    },
  });

  useEffect(() => {
    if (settled) {
      getWebApp()?.HapticFeedback?.notificationOccurred("success");
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    }
  }, [settled, queryClient]);

  return (
    <Card>
      <CardContent className="space-y-4 p-4 text-right" dir="rtl">
        <div className="flex items-center justify-between">
          <p className="font-bold">
            {cryptoAssetLabel(live.coin)} · {cryptoAssetLabel(live.network)}
          </p>
          <Badge variant={status.tone}>{status.label}</Badge>
        </div>

        {settled ? (
          <p className="py-6 text-center text-3xl">🎉</p>
        ) : (
          <>
            <div className="flex justify-center rounded-xl bg-white p-4">
              <QRCode value={live.deposit_address} size={168} />
            </div>
            <div className="space-y-2">
              <CopyRow label="آدرس واریز" value={live.deposit_address} />
              {live.memo && <CopyRow label="ممو (الزامی!)" value={live.memo} />}
              <CopyRow label={`مبلغ دقیق (${cryptoAssetLabel(live.coin)})`} value={live.expected_crypto} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">معادل</span>
              <span className="font-bold">{formatToman(live.quoted_toman)}</span>
            </div>
            {live.expires_at && live.status === "pending" && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">انقضا</span>
                <Countdown expiresAt={live.expires_at} />
              </div>
            )}
            {live.memo && (
              <p className="text-xs text-destructive">
                ⚠️ حتماً ممو را در تراکنش وارد کنید، در غیر این صورت پرداخت شناسایی نمی‌شود.
              </p>
            )}
            {tonUrl && (
              <Button asChild className="w-full">
                <a href={tonUrl}>🌐 باز کردن کیف گرام(تون) (پرکردن خودکار)</a>
              </Button>
            )}
          </>
        )}
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={onClose}>
            بازگشت
          </Button>
          {live.status === "pending" && (
            <Button
              variant="destructive"
              className="flex-1"
              disabled={cancel.isPending}
              onClick={() => {
                if (confirm("لغو این پرداخت؟")) cancel.mutate();
              }}
            >
              {cancel.isPending ? "در حال لغو…" : "لغو پرداخت"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function CryptoTab() {
  const { data: methods } = useQuery({ queryKey: ["methods"], queryFn: getPaymentMethods });
  const { data: invoices } = useQuery({ queryKey: ["crypto-invoices"], queryFn: getCryptoInvoices });
  const [coinKey, setCoinKey] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [activeInvoice, setActiveInvoice] = useState<CryptoInvoice | null>(null);
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: () => createCryptoInvoice(coinKey!, parseAmount(amount)),
    onSuccess: (invoice) => {
      setActiveInvoice(invoice);
      queryClient.invalidateQueries({ queryKey: ["crypto-invoices"] });
    },
  });

  if (activeInvoice) {
    return <InvoiceView invoice={activeInvoice} onClose={() => setActiveInvoice(null)} />;
  }

  const pending = invoices?.filter((i) => i.status === "pending") ?? [];
  const coins = methods?.crypto_coins ?? [];
  const errorMessage =
    create.error instanceof ApiError ? create.error.message : create.error ? "خطا در ایجاد فاکتور" : null;

  return (
    <div className="space-y-4 text-right" dir="rtl">
      {pending.length > 0 && (
        <Card className="border-primary/50">
          <CardContent className="space-y-2 p-4">
            <p className="text-sm font-bold">⏳ پرداخت در انتظار دارید</p>
            {pending.map((invoice) => (
              <Button
                key={invoice.id}
                variant="outline"
                size="sm"
                className="w-full justify-between"
                onClick={() => setActiveInvoice(invoice)}
              >
                <span>
                  {cryptoAssetLabel(invoice.coin)} · {formatToman(invoice.quoted_toman)}
                </span>
                <span>ادامه ←</span>
              </Button>
            ))}
          </CardContent>
        </Card>
      )}

      {coins.length === 0 ? (
        <p className="pt-6 text-center text-sm text-muted-foreground">
          پرداخت کریپتو در حال حاضر فعال نیست.
        </p>
      ) : (
        <>
          <div className="space-y-2">
            <p className="text-sm font-semibold">۱. انتخاب ارز</p>
            {coins.map((coin) => (
              <Button
                key={coin.key}
                variant={coinKey === coin.key ? "default" : "outline"}
                className="w-full justify-between"
                onClick={() => setCoinKey(coin.key)}
              >
                <span>{coin.key === "TON" ? "⭐ " : ""}{cryptoAssetLabel(coin.label)}</span>
              </Button>
            ))}
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold">۲. مبلغ (تومان)</p>
            <Input
              inputMode="numeric"
              dir="ltr"
              className="text-center"
              placeholder="500,000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
          <Button
            className="w-full"
            disabled={!coinKey || parseAmount(amount) <= 0 || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? "در حال ایجاد فاکتور…" : "ایجاد فاکتور پرداخت"}
          </Button>
        </>
      )}
    </div>
  );
}

function RialTab() {
  const { data: methods, refetch: refetchMethods, isFetching } = useQuery({
    queryKey: ["methods"],
    queryFn: getPaymentMethods,
  });
  const [amount, setAmount] = useState("");
  const [card, setCard] = useState("");
  const [result, setResult] = useState<RialRequest | null>(null);

  const minAmount = methods?.rial.min_amount_toman ?? 0;

  const queryClient = useQueryClient();
  const { data: rialRequests } = useQuery({ queryKey: ["rial-requests"], queryFn: getRialRequests });
  const submittedRequests =
    rialRequests?.filter(
      (r) =>
        r.status === "pending" &&
        r.payment_mode === "receipt_bot" &&
        r.receipt_status === "submitted"
    ) ?? [];

  const submit = useMutation({
    mutationFn: () =>
      createRialRequest({
        amount_toman: parseAmount(amount),
        source_card: card.replace(/[^0-9]/g, ""),
      }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["rial-requests"] });
    },
  });

  if (result) {
    // The customizable rial_payment_request template is Markdown; strip the
    // bold/code markers for clean display in the webview.
    const messageText = (result.message_text ?? "").replace(/```/g, "").replace(/\*\*/g, "").trim();
    const copyText = result.copy_text ?? result.request_text;
    const isReceiptBot = result.payment_mode === "receipt_bot";
    return (
      <Card className="text-right" dir="rtl">
        <CardContent className="space-y-4 p-4">
          <p className="font-bold">
            {isReceiptBot ? "✅ اطلاعات پرداخت آماده شد" : "✅ درخواست ثبت شد"}
          </p>
          <p className="text-sm leading-6 text-muted-foreground">
            {isReceiptBot
              ? "مبلغ را به کارت نمایش داده‌شده واریز کنید و سپس رسید را داخل بات اصلی ارسال کنید."
              : "متن زیر را بدون تغییر برای ادمین ارسال کنید تا پس از بررسی، کیف پولتان شارژ شود."}
          </p>
          <div className="rounded-lg bg-muted/70 p-3 text-xs text-muted-foreground">
            تاریخ ثبت: <span className="text-foreground">{formatTehranDateTime(result.created_at, false)}</span>
          </div>
          {isReceiptBot && result.destination_card && (
            <DestinationCardBox
              card={result.destination_card}
              holder={result.destination_holder}
            />
          )}
          {isReceiptBot && result.expires_at && (
            <p className="rounded-lg bg-destructive/10 p-3 text-xs font-medium text-destructive">
              اعتبار پرداخت تا ساعت <span dir="ltr">{formatTehranTime(result.expires_at)}</span> تهران است.
            </p>
          )}
          {messageText && (
            <div className="whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs leading-6">
              {messageText}
            </div>
          )}
          {!isReceiptBot && <CopyRow label="متن آماده برای ارسال به ادمین" value={copyText} />}
          {result.receipt_bot_url && (
            <Button
              className="w-full"
              onClick={() => {
                const tg = getWebApp();
                if (tg) tg.openTelegramLink(result.receipt_bot_url!);
                else window.location.href = result.receipt_bot_url!;
              }}
            >
              📸 ارسال رسید در بات اصلی
            </Button>
          )}
          {result.send_url && (
            <Button asChild className="w-full">
              <a href={result.send_url}>📩 ارسال به ادمین</a>
            </Button>
          )}
          <Button variant="outline" className="w-full" onClick={() => setResult(null)}>
            درخواست جدید
          </Button>
        </CardContent>
      </Card>
    );
  }

  const needsPhoneVerification =
    Boolean(methods?.rial.phone_required) && !methods?.rial.phone_verified;
  if (needsPhoneVerification) {
    const verifyUrl = methods?.rial.verify_phone_url;
    return (
      <Card>
        <CardContent className="space-y-4 p-4 text-right" dir="rtl">
          <div className="space-y-2">
            <p className="text-center text-2xl">📱</p>
            <p className="font-bold">تایید شماره اکانت تلگرام</p>
            <p className="text-sm leading-6 text-muted-foreground">
              برای پرداخت کارت‌به‌کارت باید شماره ایران متعلق به همین اکانت را داخل ربات ارسال و تایید کنید.
            </p>
          </div>
          <Button
            className="min-h-12 w-full"
            disabled={!verifyUrl}
            onClick={() => {
              if (!verifyUrl) return;
              const tg = getWebApp();
              if (tg) tg.openTelegramLink(verifyUrl);
              else window.location.href = verifyUrl;
            }}
          >
            ارسال شماره و تایید در ربات
          </Button>
          <Button
            variant="outline"
            className="min-h-11 w-full"
            disabled={isFetching}
            onClick={() => refetchMethods()}
          >
            {isFetching ? "در حال بررسی…" : "شماره را تایید کردم؛ بررسی مجدد"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  const cardDigits = card.replace(/[^0-9]/g, "");
  const valid =
    parseAmount(amount) >= minAmount &&
    cardDigits.length === 16;
  const errorMessage =
    submit.error instanceof ApiError ? submit.error.message : submit.error ? "خطا در ثبت درخواست" : null;

  return (
    <div className="space-y-4 text-right" dir="rtl">
      {submittedRequests.length > 0 && (
        <Card className="border-primary/50">
          <CardContent className="space-y-3 p-4">
            <p className="text-sm font-bold">⏳ رسیدهای ارسال‌شده در انتظار بررسی</p>
            {submittedRequests.map((req) => (
              <div key={req.id} className="rounded-lg bg-muted/70 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">مبلغ:</span>
                  <span className="font-bold">{formatToman(req.amount_toman)}</span>
                </div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">کد پیگیری:</span>
                  <span className="font-mono text-xs" dir="ltr">{req.tracking_code}</span>
                </div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">تاریخ ثبت:</span>
                  <span className="text-xs">{formatTehranDateTime(req.created_at, false)}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      <div className="space-y-2">
        <p className="text-sm font-semibold">مبلغ (تومان)</p>
        <Input
          inputMode="numeric"
          dir="ltr"
          className="text-center"
          placeholder={minAmount ? `حداقل ${minAmount.toLocaleString("fa-IR")}` : ""}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <p className="text-sm font-semibold">شماره کارت مبدا (۱۶ رقم)</p>
        <Input
          inputMode="numeric"
          dir="ltr"
          className="text-center"
          placeholder="6037-xxxx-xxxx-xxxx"
          value={card}
          onChange={(e) => setCard(e.target.value)}
        />
      </div>
      {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
      <Button className="w-full" disabled={!valid || submit.isPending} onClick={() => submit.mutate()}>
        {submit.isPending ? "در حال ثبت…" : "ثبت درخواست"}
      </Button>
    </div>
  );
}

function HooshPayStatus({ invoice, expired }: { invoice: HooshPayInvoice; expired?: boolean }) {
  const tone =
    invoice.status === "paid" || invoice.credited_at
      ? "default"
      : expired || invoice.status === "failed"
        ? "destructive"
        : "secondary";
  const label = invoice.credited_at
    ? "شارژ شد"
    : invoice.status === "paid"
      ? "پرداخت شد"
      : expired
        ? "منقضی شد"
        : invoice.status === "pending"
          ? "در انتظار پرداخت"
          : invoice.status;
  return <Badge variant={tone}>{label}</Badge>;
}

function HooshPayCountdown({ expiresAt }: { expiresAt: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const end = dateMs(expiresAt) ?? now;
  const remaining = Math.max(0, end - now);
  if (remaining <= 0) {
    return (
      <span className="text-sm font-bold text-destructive">
        مهلت پرداخت تمام شده است
      </span>
    );
  }
  const hours = Math.floor(remaining / 3_600_000);
  const minutes = Math.floor((remaining % 3_600_000) / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1000);
  return (
    <span dir="ltr" className="font-mono text-lg font-bold tabular-nums text-primary">
      {hours > 0 ? `${String(hours).padStart(2, "0")}:` : ""}
      {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
    </span>
  );
}

function HooshPayTab() {
  const queryClient = useQueryClient();
  const { data: methods } = useQuery({ queryKey: ["methods"], queryFn: getPaymentMethods });
  const { data: invoices } = useQuery({ queryKey: ["hooshpay-invoices"], queryFn: getHooshPayInvoices });
  const [amount, setAmount] = useState("");
  const [invoice, setInvoice] = useState<HooshPayInvoice | null>(null);
  const minAmount = methods?.hooshpay.min_amount_toman ?? 0;
  const enabled = methods?.hooshpay.enabled ?? false;
  const hooshpayTitle = methods?.hooshpay.title || "درگاه هوش‌پی";
  const hooshpaySubtitle =
    methods?.hooshpay.subtitle ||
    "پرداخت کارت‌به‌کارت آنی، بدون احراز و همراه با کارمزد.";
  const amountLabel = methods?.hooshpay.amount_label || "مبلغ شارژ کیف پول (تومان)";
  const createButtonLabel = methods?.hooshpay.create_button || "ساخت لینک پرداخت هوش‌پی";
  const payButtonLabel = methods?.hooshpay.pay_button || "پرداخت با هوش‌پی";
  const presetAmounts = methods?.hooshpay.preset_amounts ?? [];

  const create = useMutation({
    mutationFn: (amountOverride?: number) => createHooshPayInvoice(amountOverride ?? parseAmount(amount)),
    onSuccess: (data) => {
      setInvoice(data);
      setAmount("");
      queryClient.invalidateQueries({ queryKey: ["hooshpay-invoices"] });
    },
  });
  const verify = useMutation({
    mutationFn: (id: number) => verifyHooshPayInvoice(id),
    onSuccess: (data) => {
      setInvoice(data);
      queryClient.invalidateQueries({ queryKey: ["hooshpay-invoices"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const activeInvoice = invoice ?? invoices?.[0] ?? null;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!activeInvoice?.expires_at || activeInvoice.credited_at) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [activeInvoice?.expires_at, activeInvoice?.credited_at]);
  const activeInvoiceExpiresAt = dateMs(activeInvoice?.expires_at);
  const activeInvoiceExpired = Boolean(
    activeInvoiceExpiresAt &&
      activeInvoiceExpiresAt <= now &&
      !activeInvoice?.credited_at &&
      activeInvoice?.status !== "paid"
  );

  if (!enabled) {
    return (
      <Card>
        <CardContent className="space-y-2 p-4 text-center text-sm text-muted-foreground">
          درگاه هوش‌پی در حال حاضر غیرفعال است.
        </CardContent>
      </Card>
    );
  }

  const valid = parseAmount(amount) >= minAmount;
  const errorMessage =
    create.error instanceof ApiError ? create.error.message : create.error ? "ساخت فاکتور انجام نشد" : null;

  return (
    <div className="space-y-4 text-right" dir="rtl">
      <Card>
        <CardContent className="space-y-4 p-4">
          <div>
            <p className="text-sm font-bold">⚡️ {hooshpayTitle}</p>
            <p className="mt-1 text-xs leading-6 text-muted-foreground">
              {hooshpaySubtitle}
            </p>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold">{amountLabel}</p>
            <Input
              inputMode="numeric"
              dir="ltr"
              className="text-center"
              placeholder={minAmount ? `حداقل ${minAmount.toLocaleString("fa-IR")}` : ""}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            {presetAmounts.length > 0 && (
              <div className="grid grid-cols-2 gap-2">
                {presetAmounts.map((preset) => (
                  <Button
                    key={preset}
                    type="button"
                    variant={parseAmount(amount) === preset ? "default" : "secondary"}
                    className="min-h-11"
                    onClick={() => setAmount(String(preset))}
                  >
                    {formatToman(preset)}
                  </Button>
                ))}
              </div>
            )}
          </div>
          {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
          <Button className="w-full" disabled={!valid || create.isPending} onClick={() => create.mutate(undefined)}>
            {create.isPending ? "در حال ساخت فاکتور…" : createButtonLabel}
          </Button>
        </CardContent>
      </Card>

      {activeInvoice && (
        <Card className="border-primary/40 text-right" dir="rtl">
          <CardContent className="space-y-3 p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-bold">آخرین فاکتور هوش‌پی</p>
              <HooshPayStatus invoice={activeInvoice} expired={activeInvoiceExpired} />
            </div>
            <div className="grid gap-2 text-sm">
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">مبلغ شارژ:</span>
                <span>{formatToman(activeInvoice.amount_toman)}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">مبلغ قابل پرداخت:</span>
                <span>{formatToman(activeInvoice.payable_amount ?? activeInvoice.amount_toman)}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">کد پیگیری:</span>
                <span dir="ltr">{activeInvoice.order_id}</span>
              </div>
              {activeInvoice.expires_at && !activeInvoice.credited_at && (
                <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-center">
                  <p className="text-xs font-medium text-muted-foreground">
                    {activeInvoiceExpired ? "وضعیت مهلت پرداخت" : "مهلت پرداخت باقی‌مانده"}
                  </p>
                  <HooshPayCountdown expiresAt={activeInvoice.expires_at} />
                  <p className="mt-1 text-xs text-muted-foreground">
                    اعتبار پرداخت تا ساعت <span dir="ltr">{formatTehranTime(activeInvoice.expires_at)}</span> تهران است.
                  </p>
                </div>
              )}
              <p className="rounded-lg bg-destructive/10 p-3 text-xs leading-6 text-destructive">
                حتماً مبلغ قابل پرداخت را دقیق واریز کنید؛ مسئولیت واریز مبلغ اشتباه یا کارت اشتباه با شماست.
              </p>
            </div>
            {activeInvoice.payment_url && !activeInvoice.credited_at && !activeInvoiceExpired && (
              <Button
                className="w-full"
                onClick={() => {
                  const tg = getWebApp();
                  if (tg?.openLink) tg.openLink(activeInvoice.payment_url!);
                  else window.location.href = activeInvoice.payment_url!;
                }}
              >
                {payButtonLabel}
              </Button>
            )}
            {activeInvoiceExpired && !activeInvoice.credited_at && (
              <Button
                className="w-full"
                disabled={create.isPending}
                onClick={() => create.mutate(activeInvoice.amount_toman)}
              >
                {create.isPending ? "در حال ساخت لینک جدید…" : "مهلت فاکتور تمام شده؛ ساخت لینک پرداخت جدید"}
              </Button>
            )}
            <Button
              variant="outline"
              className="w-full"
              disabled={verify.isPending}
              onClick={() => verify.mutate(activeInvoice.id)}
            >
              {verify.isPending ? "در حال بررسی…" : "بررسی وضعیت پرداخت"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TransactionsList() {
  const { data: transactions, isLoading } = useQuery({
    queryKey: ["transactions"],
    queryFn: getTransactions,
  });
  if (isLoading) return <Skeleton className="h-24 w-full rounded-xl" />;
  if (!transactions?.length) return null;
  return (
    <div className="space-y-2">
      <Separator />
      <p className="pt-2 text-sm font-semibold">تاریخچه تراکنش‌ها</p>
      {transactions.slice(0, 10).map((t) => (
        <div key={t.id} className="flex items-center justify-between py-1 text-sm">
          <span className="text-muted-foreground">
            {formatTehranDateTime(t.created_at, false)}
          </span>
          <span className={t.amount >= 0 ? "font-bold text-green-600" : "font-bold"}>
            {t.amount >= 0 ? "+" : ""}
            {formatToman(t.amount)}
          </span>
        </div>
      ))}
    </div>
  );
}

function CouponCard() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [applied, setApplied] = useState<AppliedCoupon | null>(null);
  const coupon = useMutation({
    mutationFn: () => applyCoupon(code.trim()),
    onSuccess: (result) => {
      setApplied(result);
      setCode("");
      getWebApp()?.HapticFeedback?.notificationOccurred("success");
      queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
    onError: () => getWebApp()?.HapticFeedback?.notificationOccurred("error"),
  });

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div>
          <p className="text-sm font-bold">🎁 کد تخفیف</p>
          <p className="mt-1 text-xs text-muted-foreground">
            کد تخفیف درصدی یا اعتبار مبلغی را اینجا فعال کنید؛ مقدار آن در بخش خرید سرویس از قیمت کم می‌شود.
          </p>
        </div>
        {applied ? (
          <div className="rounded-lg bg-primary/10 p-3 text-sm text-primary">
            کد <span className="font-bold" dir="ltr">{applied.code}</span> فعال شد:{" "}
            {applied.discount_type === "percent"
              ? `${applied.amount.toLocaleString("fa-IR")}٪ تخفیف`
              : `${formatToman(applied.amount)} اعتبار تخفیف`}
          </div>
        ) : (
          <div className="flex gap-2">
            <Input
              dir="ltr"
              className="text-center"
              placeholder="کد تخفیف"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
            <Button
              variant="secondary"
              disabled={!code.trim() || coupon.isPending}
              onClick={() => coupon.mutate()}
            >
              {coupon.isPending ? "…" : "اعمال"}
            </Button>
          </div>
        )}
        {coupon.error && (
          <p className="text-xs text-destructive">
            {coupon.error instanceof ApiError ? coupon.error.message : "کد تخفیف معتبر نیست"}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function WalletContent() {
  const { data: me, isLoading } = useQuery({ queryKey: ["me"], queryFn: getMe });
  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">💳 کیف پول</h1>
      <Card className="bg-primary text-primary-foreground">
        <CardContent className="space-y-1 p-5">
          <p className="text-xs opacity-80">موجودی فعلی</p>
          {isLoading ? (
            <Skeleton className="h-8 w-32 bg-primary-foreground/20" />
          ) : (
            <p className="text-2xl font-bold">
              <CountUp to={me?.wallet_balance ?? 0} duration={0.45} separator="٬" locale="fa-IR" />{" "}
              تومان
            </p>
          )}
        </CardContent>
      </Card>

      <CouponCard />

      <Tabs defaultValue="crypto">
        <TabsList className="w-full" dir="rtl">
          <TabsTrigger value="crypto" className="flex-1">
            💎 کریپتو
          </TabsTrigger>
          <TabsTrigger value="rial" className="flex-1">
            🏦 کارت‌به‌کارت
          </TabsTrigger>
          <TabsTrigger value="hooshpay" className="flex-1">
            ⚡️ هوش‌پی
          </TabsTrigger>
        </TabsList>
        <TabsContent value="crypto" className="pt-3">
          <CryptoTab />
        </TabsContent>
        <TabsContent value="rial" className="pt-3">
          <RialTab />
        </TabsContent>
        <TabsContent value="hooshpay" className="pt-3">
          <HooshPayTab />
        </TabsContent>
      </Tabs>

      <TransactionsList />
    </div>
  );
}

export default function WalletPage() {
  return (
    <AuthGate>
      <WalletContent />
    </AuthGate>
  );
}
