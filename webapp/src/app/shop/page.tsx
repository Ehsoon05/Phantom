"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  applyCoupon,
  buyPlan,
  formatToman,
  getMe,
  getPlans,
  type AppliedCoupon,
  type Plan,
  type Purchase,
} from "@/lib/api";
import { getWebApp } from "@/lib/telegram";

function PlanCard({ plan, onSelect }: { plan: Plan; onSelect: (plan: Plan) => void }) {
  const hasDiscount = plan.discount_amount > 0 && plan.price != null;
  return (
    <Card
      className={!plan.in_stock ? "opacity-50" : "active:scale-[0.98] transition-transform"}
      onClick={() => plan.in_stock && onSelect(plan)}
    >
      <CardContent className="flex items-center justify-between p-4">
        <div className="space-y-1">
          <p className="font-bold">
            {plan.emoji ? `${plan.emoji} ` : ""}
            {plan.title}
          </p>
          <p className="text-xs text-muted-foreground">{plan.volume_gb} گیگابایت</p>
        </div>
        <div className="text-left">
          {!plan.in_stock ? (
            <Badge variant="secondary">ناموجود</Badge>
          ) : (
            <>
              {hasDiscount && (
                <p className="text-xs text-muted-foreground line-through">
                  {formatToman(plan.price!)}
                </p>
              )}
              <p className="font-bold text-primary">
                {plan.final_price != null ? formatToman(plan.final_price) : "—"}
              </p>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ShopContent() {
  const queryClient = useQueryClient();
  const { data: categories, isLoading } = useQuery({ queryKey: ["plans"], queryFn: getPlans });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const [selected, setSelected] = useState<Plan | null>(null);
  const [result, setResult] = useState<Purchase | null>(null);
  const [couponCode, setCouponCode] = useState("");
  const [applied, setApplied] = useState<AppliedCoupon | null>(null);

  const coupon = useMutation({
    mutationFn: () => applyCoupon(couponCode.trim()),
    onSuccess: (c) => {
      setApplied(c);
      setCouponCode("");
      getWebApp()?.HapticFeedback?.notificationOccurred("success");
      queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
    onError: () => getWebApp()?.HapticFeedback?.notificationOccurred("error"),
  });

  const purchase = useMutation({
    mutationFn: (plan: Plan) => buyPlan(plan.id, crypto.randomUUID()),
    onSuccess: (data) => {
      setResult(data);
      setSelected(null);
      getWebApp()?.HapticFeedback?.notificationOccurred("success");
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      queryClient.invalidateQueries({ queryKey: ["purchases"] });
    },
    onError: () => getWebApp()?.HapticFeedback?.notificationOccurred("error"),
  });

  const balance = me?.wallet_balance ?? 0;
  const price = selected?.final_price ?? 0;
  const insufficient = selected != null && balance < price;
  const errorMessage =
    purchase.error instanceof ApiError ? purchase.error.message : purchase.error ? "خطا در خرید" : null;

  if (isLoading) {
    return (
      <div className="space-y-3 pt-2">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-bold">🛍 خرید سرویس</h1>

      <Card>
        <CardContent className="space-y-2 p-4">
          {applied ? (
            <p className="text-sm text-green-600">
              ✅ کوپن <span dir="ltr" className="font-bold">{applied.code}</span> اعمال شد —{" "}
              {applied.discount_type === "percent"
                ? `${applied.amount}%`
                : formatToman(applied.amount)}{" "}
              تخفیف
            </p>
          ) : (
            <>
              <div className="flex gap-2">
                <Input
                  dir="ltr"
                  className="text-center"
                  placeholder="کد تخفیف"
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value)}
                />
                <Button
                  variant="secondary"
                  disabled={!couponCode.trim() || coupon.isPending}
                  onClick={() => coupon.mutate()}
                >
                  {coupon.isPending ? "…" : "اعمال"}
                </Button>
              </div>
              {coupon.error && (
                <p className="text-xs text-destructive">
                  {coupon.error instanceof ApiError ? coupon.error.message : "کد نامعتبر است"}
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {categories?.map((category) => (
        <section key={category.key} className="space-y-3">
          {categories.length > 1 && (
            <h2 className="text-sm font-semibold text-muted-foreground">
              {category.emoji ? `${category.emoji} ` : ""}
              {category.title}
            </h2>
          )}
          {category.plans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} onSelect={setSelected} />
          ))}
        </section>
      ))}
      {categories?.every((c) => c.plans.length === 0) && (
        <p className="pt-10 text-center text-sm text-muted-foreground">
          در حال حاضر سرویسی برای فروش موجود نیست.
        </p>
      )}

      {/* Checkout sheet */}
      <Sheet open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent side="bottom" className="rounded-t-2xl">
          <SheetHeader className="text-right">
            <SheetTitle>
              {selected?.emoji ? `${selected.emoji} ` : ""}
              {selected?.title}
            </SheetTitle>
            <SheetDescription>{selected?.volume_gb} گیگابایت</SheetDescription>
          </SheetHeader>
          <div className="space-y-4 p-4 pt-0">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">قیمت</span>
              <span className="font-bold">{selected ? formatToman(price) : ""}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">موجودی شما</span>
              <span className={insufficient ? "font-bold text-destructive" : "font-bold"}>
                {formatToman(balance)}
              </span>
            </div>
            {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
            {insufficient ? (
              <Button asChild className="w-full" variant="secondary">
                <a href="/wallet">موجودی کافی نیست — افزایش موجودی</a>
              </Button>
            ) : (
              <Button
                className="w-full"
                disabled={purchase.isPending}
                onClick={() => selected && purchase.mutate(selected)}
              >
                {purchase.isPending ? "در حال پردازش…" : "پرداخت از کیف پول"}
              </Button>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* Success sheet */}
      <Sheet open={result != null} onOpenChange={(open) => !open && setResult(null)}>
        <SheetContent side="bottom" className="rounded-t-2xl">
          <SheetHeader className="text-right">
            <SheetTitle>✅ خرید موفق</SheetTitle>
            <SheetDescription>سرویس شما آماده است</SheetDescription>
          </SheetHeader>
          <div className="space-y-4 p-4 pt-0">
            {result?.sub_link && (
              <div className="break-all rounded-lg bg-muted p-3 text-xs" dir="ltr">
                {result.sub_link}
              </div>
            )}
            <Button
              className="w-full"
              onClick={() => {
                if (result?.sub_link) navigator.clipboard.writeText(result.sub_link);
              }}
            >
              کپی لینک اشتراک
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default function ShopPage() {
  return (
    <AuthGate>
      <ShopContent />
    </AuthGate>
  );
}
