import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ChevronDown, ChevronUp, Search, Send } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  chargeUser,
  formatToman,
  getUsers,
  setUserBalance,
  toggleBlockUser,
  type AdminUser,
} from "@/lib/api";
import { countUsers, getUserPurchases } from "@/lib/admin-api";

const PAGE_SIZE = 25;

function formatStartDate(value: string | null) {
  if (!value) return "نامشخص";
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "نامشخص";
  return new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Tehran",
  }).format(date);
}

function telegramProfileUrl(username: string) {
  return `https://t.me/${username.replace(/^@+/, "")}`;
}

function UserDetail({ telegramId }: { telegramId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["user-purchases", telegramId],
    queryFn: () => getUserPurchases(telegramId),
  });
  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!data) return null;
  return (
    <div className="space-y-3 border-t pt-3">
      <div className="flex gap-4 text-sm">
        <span>خریدها: <b>{data.total_count}</b></span>
        <span>مجموع حجم: <b>{data.total_gb} GB</b></span>
        <span>مجموع خرج: <b>{formatToman(data.total_spent)}</b></span>
      </div>
      {data.purchases.length > 0 ? (
        <table className="w-full text-xs">
          <thead><tr className="border-b text-right text-muted-foreground">
            <th className="pb-1">سرویس</th><th className="pb-1">حجم</th><th className="pb-1">قیمت</th><th className="pb-1">کوپن</th><th className="pb-1">تاریخ</th>
          </tr></thead>
          <tbody>
            {data.purchases.map((p) => (
              <tr key={p.id} className="border-b last:border-0">
                <td className="py-1">{p.service_name ?? `${p.volume_gb} گیگ`}</td>
                <td className="py-1">{p.volume_gb} GB</td>
                <td className="py-1">{formatToman(p.price)}</td>
                <td className="py-1" dir="ltr">{p.coupon_code ?? "—"}</td>
                <td className="py-1 text-muted-foreground">{new Date(p.purchased_at + "Z").toLocaleDateString("fa-IR")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-xs text-muted-foreground">خریدی ثبت نشده.</p>
      )}
    </div>
  );
}

function UserRow({ user }: { user: AdminUser }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["users"] });
  const charge = useMutation({ mutationFn: (a: number) => chargeUser(user.telegram_id, a), onSuccess: invalidate });
  const setBal = useMutation({ mutationFn: (b: number) => setUserBalance(user.telegram_id, b), onSuccess: invalidate });
  const block = useMutation({ mutationFn: () => toggleBlockUser(user.telegram_id), onSuccess: invalidate });

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <p className="font-bold">{user.first_name}</p>
              {user.username && (
                <span className="inline-flex items-center gap-1" dir="ltr">
                  <span className="text-sm text-muted-foreground">
                    @{user.username.replace(/^@+/, "")}
                  </span>
                  <Button asChild size="icon-xs" variant="ghost">
                    <a
                      href={telegramProfileUrl(user.username)}
                      target="_blank"
                      rel="noreferrer"
                      title="باز کردن گفت‌وگو در تلگرام"
                      aria-label={`باز کردن گفت‌وگوی ${user.username} در تلگرام`}
                    >
                      <Send className="size-3.5" />
                    </a>
                  </Button>
                </span>
              )}
              {user.is_blocked && <Badge variant="destructive">مسدود</Badge>}
            </div>
            <p className="text-xs text-muted-foreground" dir="ltr">ID: {user.telegram_id}</p>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CalendarClock className="size-3.5" />
              شروع ربات: <span dir="ltr">{formatStartDate(user.created_at)}</span>
            </p>
            <p className="text-sm">موجودی: <span className="font-bold">{formatToman(user.wallet_balance)}</span></p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => { const v = prompt("مبلغ شارژ (منفی=کسر):"); const a = parseInt(v ?? "", 10); if (!Number.isNaN(a) && a !== 0) charge.mutate(a); }}>شارژ</Button>
            <Button size="sm" variant="outline" onClick={() => { const v = prompt("موجودی جدید:", String(user.wallet_balance)); const b = parseInt(v ?? "", 10); if (!Number.isNaN(b) && b >= 0) setBal.mutate(b); }}>تنظیم</Button>
            <Button size="sm" variant={user.is_blocked ? "secondary" : "destructive"} onClick={() => { if (confirm(user.is_blocked ? "رفع مسدودیت؟" : "مسدود کردن؟")) block.mutate(); }}>{user.is_blocked ? "رفع مسدودی" : "مسدود"}</Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>{open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />} خریدها</Button>
          </div>
        </div>
        {open && <UserDetail telegramId={user.telegram_id} />}
      </CardContent>
    </Card>
  );
}

export function UsersPage() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const { data: users, isLoading } = useQuery({
    queryKey: ["users", search, page],
    queryFn: () => getUsers(search || undefined, PAGE_SIZE, page * PAGE_SIZE),
  });
  const { data: count } = useQuery({ queryKey: ["users-count", search], queryFn: () => countUsers(search || undefined) });

  const total = count?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">کاربران</h1>
        <span className="text-sm text-muted-foreground">{total.toLocaleString("fa-IR")} کاربر</span>
      </div>

      <form className="flex max-w-md gap-2" onSubmit={(e) => { e.preventDefault(); setPage(0); setSearch(query.trim()); }}>
        <Input placeholder="جستجو: شناسه، نام کاربری یا نام…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <Button type="submit" size="icon" variant="secondary"><Search className="size-4" /></Button>
      </form>

      {isLoading ? (
        <div className="space-y-3">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}</div>
      ) : !users?.length ? (
        <p className="py-16 text-center text-sm text-muted-foreground">کاربری یافت نشد.</p>
      ) : (
        <div className="space-y-3">{users.map((u) => <UserRow key={u.telegram_id} user={u} />)}</div>
      )}

      <div className="flex items-center justify-center gap-3">
        <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>قبلی</Button>
        <span className="text-sm text-muted-foreground">صفحه {(page + 1).toLocaleString("fa-IR")} از {pages.toLocaleString("fa-IR")}</span>
        <Button size="sm" variant="outline" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>بعدی</Button>
      </div>
    </div>
  );
}
