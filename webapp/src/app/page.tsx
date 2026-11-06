"use client";

import { useQuery } from "@tanstack/react-query";
import { Gift, ShoppingBag, Wallet } from "lucide-react";
import Link from "next/link";

import { AuthGate } from "@/components/auth-gate";
import CountUp from "@/components/reactbits/CountUp";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getMe } from "@/lib/api";

function HomeContent() {
  const { data: me, isLoading } = useQuery({ queryKey: ["me"], queryFn: getMe });

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-bold">سلام{me ? `، ${me.first_name}` : ""} 👋</h1>
      </header>

      <Card className="bg-primary text-primary-foreground">
        <CardContent className="space-y-1 p-5">
          <p className="text-xs opacity-80">موجودی کیف پول</p>
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

      <div className="grid grid-cols-3 gap-3">
        <Button asChild variant="outline" className="h-auto flex-col gap-2 py-4">
          <Link href="/shop">
            <ShoppingBag className="size-5" />
            خرید سرویس
          </Link>
        </Button>
        <Button asChild variant="outline" className="h-auto flex-col gap-2 py-4">
          <Link href="/wallet">
            <Wallet className="size-5" />
            افزایش موجودی
          </Link>
        </Button>
        <Button asChild variant="outline" className="h-auto flex-col gap-2 py-4">
          <Link href="/referrals">
            <Gift className="size-5" />
            دعوت دوستان
          </Link>
        </Button>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <AuthGate>
      <HomeContent />
    </AuthGate>
  );
}
