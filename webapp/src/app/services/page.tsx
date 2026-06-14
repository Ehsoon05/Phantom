"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, Smartphone } from "lucide-react";
import { useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getPurchases,
  happLink,
  hiddifyLink,
  streisandLink,
  v2boxLink,
  v2rayNgLink,
} from "@/lib/api";
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
  const { data: purchases, isLoading } = useQuery({
    queryKey: ["purchases"],
    queryFn: getPurchases,
  });

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 2200);
  };

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
            <div className="flex items-center justify-between">
              <p className="font-bold">
                {purchase.service_name ?? `${purchase.volume_gb} گیگ`}
              </p>
              <p className="text-xs text-muted-foreground">
                {new Date(purchase.purchased_at).toLocaleDateString("fa-IR")}
              </p>
            </div>
            {purchase.sub_link && (
              <div className="space-y-3">
                <Button
                  className="min-h-12 w-full text-sm font-bold"
                  onClick={() => copySubscription(purchase.sub_link!)}
                >
                  <Copy className="size-4" />
                  کپی لینک اشتراک
                </Button>
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
