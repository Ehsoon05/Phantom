import {
  CreditCard,
  Cable,
  Gift,
  LayoutDashboard,
  LogOut,
  Megaphone,
  Package,
  Settings,
  Shield,
  Store,
  UserRoundCog,
  Users,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import ShinyText from "@/components/reactbits/ShinyText";
import { Button } from "@/components/ui/button";
import { getPermissions, hasPermission, logout } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Layout() {
  const { isOwner } = getPermissions();
  const navItems = [
    { to: "/", label: "داشبورد", icon: LayoutDashboard, end: true, show: true },
    { to: "/users", label: "کاربران", icon: Users, end: false, show: hasPermission("users") },
    { to: "/payments", label: "پرداخت‌ها", icon: CreditCard, end: false, show: hasPermission("users") || hasPermission("reports") },
    { to: "/catalog", label: "محصولات", icon: Package, end: false, show: hasPermission("prices") || hasPermission("inventory") },
    { to: "/panel-bridges", label: "پنل‌ها و سرویس‌ها", icon: Cable, end: false, show: hasPermission("shop") },
    { to: "/promotions", label: "تخفیف و دعوت", icon: Gift, end: false, show: hasPermission("coupons") || hasPermission("users") },
    { to: "/shop", label: "فروشگاه", icon: Store, end: false, show: hasPermission("shop") },
    { to: "/settings", label: "تنظیمات", icon: Settings, end: false, show: hasPermission("shop") },
    { to: "/broadcast", label: "پیام همگانی", icon: Megaphone, end: false, show: hasPermission("users") },
    { to: "/sellers", label: "همکاران فروش", icon: UserRoundCog, end: false, show: isOwner },
    { to: "/admins", label: "مدیران", icon: Shield, end: false, show: isOwner },
  ].filter((item) => item.show);

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="sticky top-0 z-40 flex shrink-0 items-center gap-2 overflow-x-auto border-b bg-card/95 px-3 py-2 backdrop-blur md:h-dvh md:w-56 md:flex-col md:items-stretch md:gap-0 md:overflow-visible md:border-b-0 md:border-l md:px-3 md:py-6">
        <div className="flex shrink-0 items-center gap-2 px-1 md:mb-8 md:px-2">
          <span className="text-xl">👻</span>
          <ShinyText text="فانتوم ادمین" speed={4} color="var(--foreground)" shineColor="var(--primary)" className="font-bold" />
        </div>
        <nav className="flex gap-1 md:flex-1 md:flex-col">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex min-h-10 items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <Button variant="ghost" size="sm" className="md:justify-start" onClick={logout}>
          <LogOut className="size-4" />
          <span>خروج</span>
        </Button>
      </aside>
      <main className="min-w-0 flex-1 p-3 sm:p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
