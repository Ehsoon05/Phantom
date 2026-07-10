"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, RefreshCcw, Smartphone } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatToman,
  getPurchases,
  getMe,
  happLink,
  hiddifyLink,
  renewPurchase,
  streisandLink,
  type Purchase,
  v2boxLink,
  v2rayNgLink,
} from "@/lib/api";
import { formatTehranDateTime } from "@/lib/date";
import { getWebApp } from "@/lib/telegram";

async function copyText(value: string) {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
}

// Open an app deep link (happ://, v2rayng://, …) WITHOUT navigating the
// Mini App's own webview. Setting window.location.href to a custom scheme
// unloads/white-screens the webview when the OS has no handler; a transient
// anchor click lets the OS hand off to the app while the SPA stays alive.
function openExternal(url: string) {
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } catch {
    /* no installed handler — the link is already copied as a fallback */
  }
}

function ServicesContent() {
  const [notice, setNotice] = useState<string | null>(null);
  const [renewTarget, setRenewTarget] = useState<Purchase | null>(null);
  const queryClient = useQueryClient();
  const { data: purchases, isLoading } = useQuery({
    queryKey: ["purchases"],
    queryFn: getPurchases,
  });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const renew = useMutation({
    mutationFn: (purchaseId: number) => renewPurchase(purchaseId),
    onSuccess: () => {
      getWebApp()?.HapticFeedback?.notificationOccurred("success");
      showNotice("سرویس با موفقیت تمدید شد.");
      setRenewTarget(null);
      queryClient.invalidateQueries({ queryKey: ["purchases"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: () => {
      getWebApp()?.HapticFeedback?.notificationOccurred("error");
      showNotice("تمدید انجام نشد؛ موجودی یا وضعیت سرویس را بررسی کنید.");
    },
  });

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 2200);
  };

  const renewPrice = renewTarget?.renewal_price ?? renewTarget?.price ?? 0;
  const balance = me?.wallet_balance ?? 0;
  const renewInsufficient = renewTarget != null && balance < renewPrice;

  const copySubscription = async (subLink: string) => {
    await copyText(subLink);
    getWebApp()?.HapticFeedback?.notificationOccurred("success");
    showNotice("لینک اشتراک با موفقیت کپی شد.");
  };

  const openClient = async (subLink: string, url: string, appName: string) => {
    await copyText(subLink);
    getWebApp()?.HapticFeedback?.notificationOccurred("success");
    showNotice(`لینک کپی شد؛ در حال باز کردن ${appName}…`);
    openExternal(url);
  };

  if (isLoading) {
    return (
      <div className="space-y-3 pt-2">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {notice && (
        <div
          role="status"
          className="fixed inset-x-4 top-4 z-50 mx-auto flex max-w-sm items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-3 text-sm font-medium text-background shadow-lg"
        >
          <Check className="size-4" />
          {notice}
        </div>
      )}
      <h1 className="text-lg font-bold">⚡️ سرویس‌های من</h1>
      {!purchases?.length && (
        <p className="pt-10 text-center text-sm text-muted-foreground">
          هنوز سرویسی نخریده‌اید.
        </p>
      )}
      {purchases?.map((purchase) => (
        <Card key={purchase.id}>
          <CardContent className="space-y-3 p-4">
            <div className="space-y-1">
              <p className="font-bold">
                {purchase.service_name ?? `${purchase.volume_gb} گیگ`}
              </p>
              <p className="text-xs leading-5 text-muted-foreground">
                <span className="font-medium text-foreground">تاریخ خرید: </span>
                <span>{formatTehranDateTime(purchase.purchased_at, false)}</span>
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              {purchase.volume_label} · {formatToman(purchase.price)}
            </p>
            {purchase.sub_link && (
              <div className="space-y-3">
                <Button
                  className="min-h-12 w-full text-sm font-bold"
                  onClick={() => copySubscription(purchase.sub_link!)}
                >
                  <Copy className="size-4" />
                  کپی لینک اشتراک
                </Button>
                {purchase.can_renew && (
                  <Button
                    variant="outline"
                    className="min-h-11 w-full"
                    disabled={renew.isPending}
                    onClick={() => setRenewTarget(purchase)}
                  >
                    <RefreshCcw className="size-4" />
                    تمدید سرویس
                  </Button>
                )}
                <p className="text-xs text-muted-foreground">
                  اتصال سریع به برنامه
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => openClient(purchase.sub_link!, happLink(purchase.sub_link!), "Happ")}
                  >
                    Happ
                  </Button>
                  <Button
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => openClient(purchase.sub_link!, v2rayNgLink(purchase.sub_link!), "V2rayNG")}
                  >
                    V2rayNG
                  </Button>
                  <Button
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => openClient(purchase.sub_link!, hiddifyLink(purchase.sub_link!), "Hiddify")}
                  >
                    Hiddify
                  </Button>
                  <Button
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => openClient(purchase.sub_link!, v2boxLink(purchase.sub_link!), "V2Box")}
                  >
                    V2Box
                  </Button>
                  <Button
                    variant="secondary"
                    className="col-span-2 min-h-11"
                    onClick={() => openClient(purchase.sub_link!, streisandLink(), "Streisand")}
                  >
                    <Smartphone className="size-4" />
                    Streisand
                  </Button>
                </div>
                <Button asChild variant="outline" className="min-h-11 w-full">
                  <a href={purchase.sub_link} target="_blank" rel="noreferrer">
                    <ExternalLink className="size-4" />
                    باز کردن پنل اشتراک
                  </a>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
      <Sheet open={renewTarget != null} onOpenChange={(open) => !open && setRenewTarget(null)}>
        <SheetContent side="bottom" className="rounded-t-2xl">
          <SheetHeader className="text-right">
            <SheetTitle>تمدید سرویس</SheetTitle>
            <SheetDescription>
              {renewTarget?.service_name ?? "سرویس انتخاب‌شده"}
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-4 p-4 pt-0">
            <p className="text-sm leading-6 text-muted-foreground">
              تمدید این سرویس مثل خرید سرویس جدید از کیف پول شما پرداخت می‌شود. با تایید تمدید، حجم سرویس ریست می‌شود و تاریخ اعتبار از ابتدا طبق مدت همین سرویس محاسبه می‌شود.
            </p>
            <div className="space-y-2 rounded-lg bg-muted p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">مبلغ تمدید</span>
                <span className="font-bold">{formatToman(renewPrice)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">موجودی شما</span>
                <span className={renewInsufficient ? "font-bold text-destructive" : "font-bold"}>
                  {formatToman(balance)}
                </span>
              </div>
            </div>
            {renewInsufficient ? (
              <div className="space-y-3">
                <div
                  role="alert"
                  className="rounded-lg border border-destructive/30 bg-destructive/10 p-3"
                >
                  <p className="text-sm font-bold text-destructive">موجودی کیف پول کافی نیست</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    برای تمدید، حداقل {formatToman(Math.max(0, renewPrice - balance))} دیگر به کیف پول اضافه کنید.
                  </p>
                </div>
                <Button asChild className="min-h-12 w-full">
                  <Link href="/wallet">افزایش موجودی کیف پول</Link>
                </Button>
              </div>
            ) : (
              <Button
                className="min-h-12 w-full"
                disabled={!renewTarget || renew.isPending}
                onClick={() => renewTarget && renew.mutate(renewTarget.id)}
              >
                <RefreshCcw className="size-4" />
                {renew.isPending ? "در حال تمدید…" : "پرداخت و تمدید از کیف پول"}
              </Button>
            )}
            <Button
              variant="outline"
              className="min-h-11 w-full"
              onClick={() => setRenewTarget(null)}
            >
              انصراف
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default function ServicesPage() {
  return (
    <AuthGate>
      <ServicesContent />
    </AuthGate>
  );
}
