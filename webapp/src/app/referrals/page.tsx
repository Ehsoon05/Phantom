"use client";

import { useQuery } from "@tanstack/react-query";

import { AuthGate } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getMe } from "@/lib/api";
import { getWebApp } from "@/lib/telegram";

const BOT_USERNAME = process.env.NEXT_PUBLIC_BOT_USERNAME ?? "";
const MINIAPP_SHORT_NAME = process.env.NEXT_PUBLIC_MINIAPP_SHORT_NAME ?? "shop";

function ReferralsContent() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const link =
    me?.referral_code && BOT_USERNAME
      ? `https://t.me/${BOT_USERNAME}/${MINIAPP_SHORT_NAME}?startapp=ref_${me.referral_code}`
      : me?.referral_code && `ref_${me.referral_code}`;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold">🎁 دعوت دوستان</h1>
      <Card>
        <CardContent className="space-y-4 p-4">
          <p className="text-sm text-muted-foreground">
            دوستان خود را دعوت کنید و پاداش بگیرید.
          </p>
          {link && (
            <div className="break-all rounded-lg bg-muted p-3 text-xs" dir="ltr">
              {link}
            </div>
          )}
          <Button
            className="w-full"
            onClick={() => {
              if (!link) return;
              const tg = getWebApp();
              const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}`;
              if (tg) tg.openTelegramLink(shareUrl);
              else navigator.clipboard.writeText(link);
            }}
          >
            اشتراک‌گذاری در تلگرام
          </Button>
        </CardContent>
      </Card>
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
