import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ChevronDown, ChevronUp, RefreshCw, Search, Send, Trash2 } from "lucide-react";
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
import {
  countUsers,
  deleteUserPanelConfig,
  deleteUserPurchase,
  getUserPurchases,
  resetUserSubscriptionDevices,
  revokeUserSubscriptionLink,
  renewUserPurchase,
} from "@/lib/admin-api";
import { formatTehranDateTime } from "@/lib/date";

const PAGE_SIZE = 25;

function formatStartDate(value: string | null) {
  return formatTehranDateTime(value);
}

function telegramProfileUrl(username: string) {
  return `https://t.me/${username.replace(/^@+/, "")}`;
}

function volumeLabel(volumeGb: number) {
  return volumeGb > 0 ? `${volumeGb.toLocaleString("fa-IR")} گیگ` : "نامحدود";
}

function UserDetail({ telegramId }: { telegramId: number }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["user-purchases", telegramId],
    queryFn: () => getUserPurchases(telegramId),
  });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["user-purchases", telegramId] });
    qc.invalidateQueries({ queryKey: ["users"] });
  };
  const deletePurchase = useMutation({
    mutationFn: (purchaseId: number) => deleteUserPurchase(telegramId, purchaseId),
    onSuccess: invalidate,
  });
  const deletePanel = useMutation({
    mutationFn: (configId: number) => deleteUserPanelConfig(telegramId, configId),
    onSuccess: invalidate,
  });
  const renew = useMutation({
    mutationFn: (purchaseId: number) => renewUserPurchase(telegramId, purchaseId),
    onSuccess: invalidate,
  });
  const resetDevices = useMutation({
    mutationFn: (configId: number) => resetUserSubscriptionDevices(telegramId, configId),
    onSuccess: invalidate,
  });
  const revokeLink = useMutation({
    mutationFn: (configId: number) => revokeUserSubscriptionLink(telegramId, configId),
    onSuccess: invalidate,
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
            <th className="pb-1">سرویس</th><th className="pb-1">نام پنل</th><th className="pb-1">حجم</th><th className="pb-1">قیمت</th><th className="pb-1">منبع</th><th className="pb-1">وضعیت</th><th className="pb-1">تاریخ</th><th className="pb-1">عملیات</th>
          </tr></thead>
          <tbody>
            {data.purchases.map((p) => (
              <tr key={p.id} className="border-b last:border-0">
                <td className="py-2">
                  <div className="font-medium">{p.service_name ?? volumeLabel(p.volume_gb)}</div>
                  <div className="text-muted-foreground" dir="ltr">#{p.id} · {p.category_key}</div>
                  {p.public_url && (
                    <a className="block max-w-56 truncate text-[11px]" href={p.public_url} target="_blank" rel="noreferrer" dir="ltr">
                      {p.public_url}
                    </a>
                  )}
                </td>
                <td className="py-2" dir="ltr">{p.panel_username ?? "—"}</td>
                <td className="py-2">{volumeLabel(p.volume_gb)}</td>
                <td className="py-1">{formatToman(p.price)}</td>
                <td className="py-2">
                  <div dir="ltr">{p.panel_key ?? p.provision_source ?? "—"}</div>
                  {p.kind === "renewal" && <Badge variant="secondary">تمدید</Badge>}
                </td>
                <td className="py-2">
                  {p.panel_deleted_at ? <Badge variant="destructive">حذف از پنل</Badge> : <Badge variant="secondary">فعال</Badge>}
                </td>
                <td className="py-2 text-muted-foreground">{formatTehranDateTime(p.purchased_at, false)}</td>
                <td className="py-2">
                  <div className="flex flex-wrap gap-1">
                    <Button
                      size="icon-xs"
                      variant="outline"
                      title="تمدید از کیف پول کاربر"
                      disabled={renew.isPending || p.kind === "renewal" || !!p.panel_deleted_at}
                      onClick={() => {
                        if (confirm("تمدید انجام شود؟ مبلغ تمدید از کیف پول کاربر کم می‌شود.")) renew.mutate(p.id);
                      }}
                    >
                      <RefreshCw className="size-3.5" />
                    </Button>
                    <Button
                      size="icon-xs"
                      variant="outline"
                      title="حذف کانفیگ از پنل"
                      disabled={deletePanel.isPending || !!p.panel_deleted_at}
                      onClick={() => {
                        if (confirm("فقط کانفیگ این سرویس از پنل حذف شود؟")) deletePanel.mutate(p.config_id);
                      }}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      title="ریست شمارش دستگاه لینک ساب"
                      disabled={resetDevices.isPending || !p.public_sub_token}
                      onClick={() => {
                        if (confirm("شمارش دستگاه‌های این لینک ریست شود؟")) resetDevices.mutate(p.config_id);
                      }}
                    >
                      ریست دستگاه
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      title="باطل کردن لینک ساب و ساخت لینک جدید"
                      disabled={revokeLink.isPending || !p.public_sub_token}
                      onClick={() => {
                        if (confirm("لینک قبلی باطل و لینک جدید ساخته شود؟")) revokeLink.mutate(p.config_id);
                      }}
                    >
                      Revoke
                    </Button>
                    <Button
                      size="icon-xs"
                      variant="destructive"
                      title="حذف خرید از سابقه"
                      disabled={deletePurchase.isPending}
                      onClick={() => {
                        if (confirm("این خرید فقط از سابقه کاربر حذف شود؟")) deletePurchase.mutate(p.id);
                      }}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </td>
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
            <Button size="sm" variant="outline" onClick={() => { const v = prompt("مبلغ تغییر موجودی (مثبت=شارژ، منفی=کسر):"); const a = parseInt((v ?? "").replace(/,/g, ""), 10); if (!Number.isNaN(a) && a !== 0) charge.mutate(a); }}>افزایش/کسر</Button>
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
