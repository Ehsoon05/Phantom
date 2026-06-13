"use client";

import { useQuery } from "@tanstack/react-query";

import { AuthGate } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatToman, getPurchases, happLink, v2rayNgLink } from "@/lib/api";

function ServicesContent() {
  const { data: purchases, isLoading } = useQuery({
    queryKey: ["purchases"],
    queryFn: getPurchases,
  });

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
            <p className="text-xs text-muted-foreground">
              {purchase.volume_gb} گیگابایت · {formatToman(purchase.price)}
            </p>
            {purchase.sub_link && (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <Button asChild size="sm">
                    <a href={happLink(purchase.sub_link)}>افزودن به Happ</a>
                  </Button>
                  <Button asChild size="sm" variant="secondary">
                    <a href={v2rayNgLink(purchase.sub_link)}>افزودن به V2rayNG</a>
                  </Button>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => navigator.clipboard.writeText(purchase.sub_link!)}
                >
                  کپی لینک اشتراک
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
