"use client";

import { AuthGate } from "@/components/auth-gate";

export default function WalletPage() {
  return (
    <AuthGate>
      <div className="space-y-4">
        <h1 className="text-lg font-bold">💳 کیف پول</h1>
        <p className="text-sm text-muted-foreground">
          شارژ کریپتو و ریالی به‌زودی در همین صفحه — فعلاً از ربات استفاده کنید.
        </p>
      </div>
    </AuthGate>
  );
}
