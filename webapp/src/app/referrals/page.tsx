"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Gift, Share2, Users } from "lucide-react";
import { useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getReferrals } from "@/lib/api";
import { getWebApp } from "@/lib/telegram";

function plainTelegramText(value: string) {
  return value
    .replace(/<[^>]+>/g, "")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/```|`|\*\*/g, "")
    .trim();
}

function ReferralsContent() {
  const { data, isLoading } = useQuery({
    queryKey: ["referrals"],
    queryFn: getReferrals,
  });
  const [copied, setCopied] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (!data) return null;

  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(
    data.referral_link,
  )}&text=${encodeURIComponent(data.share_text)}`;

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">🎁 دعوت دوستان</h1>

      <Card>
        <CardContent className="space-y-4 p-4">
          <p className="whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
            {plainTelegramText(data.message_text)}
          </p>
          <div className="flex items-center justify-between rounded-lg bg-muted p-3">
            <div className="flex items-center gap-2">
              <Users className="size-5 text-primary" />
              <span className="text-sm">تعداد افراد دعوت‌شده</span>
            </div>
            <span className="text-lg font-bold text-primary">
              {data.total_referrals.toLocaleString("fa-IR")}
            </span>
          </div>
          <div className="break-all rounded-lg border bg-background p-3 text-xs" dir="ltr">
            {data.referral_link}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              className="min-h-11"
              onClick={async () => {
                await navigator.clipboard.writeText(data.referral_link);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? <Check /> : <Copy />}
              {copied ? "کپی شد" : "کپی لینک"}
            </Button>
            <Button
              className="min-h-11"
              onClick={() => {
                const tg = getWebApp();
                if (tg) tg.openTelegramLink(shareUrl);
                else window.location.href = shareUrl;
              }}
            >
              <Share2 />
              دعوت در تلگرام
            </Button>
          </div>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Gift className="size-5 text-primary" />
          <h2 className="font-bold">جایزه‌های فعال</h2>
        </div>
        {data.rules.length ? (
          data.rules.map((rule) => {
            const target = Math.max(rule.target_count, 1);
            const progress = Math.min(100, Math.round((rule.qualified_count / target) * 100));
            return (
              <Card key={rule.id}>
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-bold">{rule.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {rule.qualification_label}
                      </p>
                    </div>
                    <Badge
                      variant="secondary"
                      className="max-w-[48%] whitespace-normal text-center leading-5"
                    >
                      {rule.reward_text}
                    </Badge>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-[width]"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">
                      {rule.is_repeatable ? "جایزه تکرارشونده" : "جایزه یک‌باره"}
                    </span>
                    <span className="font-bold">
                      {rule.qualified_count.toLocaleString("fa-IR")} از{" "}
                      {target.toLocaleString("fa-IR")} نفر معتبر
                    </span>
                  </div>
                </CardContent>
              </Card>
            );
          })
        ) : (
          <p className="rounded-lg bg-muted p-4 text-center text-sm text-muted-foreground">
            در حال حاضر جایزه فعالی تعریف نشده است.
          </p>
        )}
      </section>
    </div>
  );
}

export default function ReferralsPage() {
  return (
    <AuthGate>
      <ReferralsContent />
    </AuthGate>
  );
}
