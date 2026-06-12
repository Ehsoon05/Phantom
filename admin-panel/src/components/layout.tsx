import { CreditCard, LayoutDashboard, LogOut, Users } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { logout } from "@/lib/api";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "داشبورد", icon: LayoutDashboard, end: true },
  { to: "/users", label: "کاربران", icon: Users, end: false },
  { to: "/payments", label: "پرداخت‌ها", icon: CreditCard, end: false },
];

export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="flex shrink-0 items-center justify-between border-b bg-card px-4 py-3 md:w-56 md:flex-col md:items-stretch md:border-b-0 md:border-l md:px-3 md:py-6">
        <div className="flex items-center gap-2 md:mb-8 md:px-2">
          <span className="text-xl">👻</span>
          <span className="font-bold">فانتوم ادمین</span>
        </div>
        <nav className="flex gap-1 md:flex-1 md:flex-col">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <Icon className="size-4" />
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
