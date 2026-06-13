"use client";

import { Gift, Home, ShoppingBag, Wallet, Zap } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const items = [
  { href: "/", label: "خانه", icon: Home },
  { href: "/shop", label: "خرید", icon: ShoppingBag },
  { href: "/wallet", label: "کیف پول", icon: Wallet },
  { href: "/services", label: "سرویس‌ها", icon: Zap },
  { href: "/referrals", label: "دعوت", icon: Gift },
];

export function BottomNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 border-t bg-background pb-[env(safe-area-inset-bottom)]">
      <div className="mx-auto flex max-w-md items-stretch justify-around">
        {items.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 py-2 text-[11px]",
                active ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon className="size-5" />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
