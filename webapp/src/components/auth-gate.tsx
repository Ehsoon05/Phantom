"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useAuthState } from "@/components/providers";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const state = useAuthState();

  if (state === "loading") {
    return (
      <div className="space-y-4 pt-8">
        <Skeleton className="h-24 w-full rounded-2xl" />
        <Skeleton className="h-12 w-full rounded-xl" />
        <Skeleton className="h-12 w-full rounded-xl" />
      </div>
    );
  }
  if (state === "outside-telegram") {
    return (
      <div className="flex min-h-[60dvh] flex-col items-center justify-center gap-3 text-center">
        <p className="text-2xl">👻</p>
        <h1 className="text-lg font-bold">فروشگاه فانتوم</h1>
        <p className="text-sm text-muted-foreground">
          این برنامه فقط داخل تلگرام قابل استفاده است.
          <br />
          لطفاً آن را از طریق ربات باز کنید.
        </p>
      </div>
    );
  }
  if (state === "error") {
    return (
      <div className="flex min-h-[60dvh] flex-col items-center justify-center gap-3 text-center">
        <p className="text-2xl">⚠️</p>
        <p className="text-sm text-muted-foreground">خطا در ورود. لطفاً دوباره تلاش کنید.</p>
      </div>
    );
  }
  return <>{children}</>;
}
