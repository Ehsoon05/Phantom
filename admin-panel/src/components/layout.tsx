import {
  CreditCard,
  Gift,
  LayoutDashboard,
  LogOut,
  Megaphone,
  Package,
  Settings,
  Shield,
  Store,
  Users,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import ShinyText from "@/components/reactbits/ShinyText";
import { Button } from "@/components/ui/button";
import { getPermissions, hasPermission, logout } from "@/lib/api";
import { cn } from "@/lib/utils";

const { isOwner } = getPermissions();

const navItems = [
  { to: "/", label: "داشبورد", icon: LayoutDashboard, end: true, show: true },
  { to: "/users", label: "کاربران", icon: Users, end: false, show: hasPermission("users") },
  { to: "/payments", label: "پرداخت‌ها", icon: CreditCard, end: false, show: hasPermission("users") || hasPermission("reports") },
  { to: "/catalog", label: "محصولات", icon: Package, end: false, show: hasPermission("prices") || hasPermission("inventory") },
  { to: "/promotions", label: "تخفیف و دعوت", icon: Gift, end: false, show: hasPermission("coupons") || hasPermission("users") },
  { to: "/shop", label: "فروشگاه", icon: Store, end: false, show: hasPermission("shop") },
  { to: "/settings", label: "تنظیمات", icon: Settings, end: false, show: hasPermission("shop") },
  { to: "/broadcast", label: "پیام همگانی", icon: Megaphone, end: false, show: hasPermission("users") },
  { to: "/admins", label: "مدیران", icon: Shield, end: false, show: isOwner },
].filter((item) => item.show);

export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="flex shrink-0 items-center gap-2 overflow-x-auto border-b bg-card px-4 py-3 md:w-56 md:flex-col md:items-stretch md:gap-0 md:overflow-visible md:border-b-0 md:border-l md:px-3 md:py-6">
        <div className="flex items-center gap-2 md:mb-8 md:px-2">
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
                  "flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              <span className="hidden sm:inline">{label}</span>
            </NavLink>
          ))}
        </nav>
        <Button variant="ghost" size="sm" className="md:justify-start" onClick={logout}>
          <LogOut className="size-4" />
          <span className="hidden sm:inline">خروج</span>
        </Button>
      </aside>
      <main className="flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
