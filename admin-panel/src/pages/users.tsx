import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
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

function UserActions({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const charge = useMutation({
    mutationFn: (amount: number) => chargeUser(user.telegram_id, amount),
    onSuccess: invalidate,
  });
  const setBalance = useMutation({
    mutationFn: (balance: number) => setUserBalance(user.telegram_id, balance),
    onSuccess: invalidate,
  });
  const block = useMutation({
    mutationFn: () => toggleBlockUser(user.telegram_id),
    onSuccess: invalidate,
  });

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={charge.isPending}
        onClick={() => {
          const input = prompt("مبلغ شارژ (تومان) — عدد منفی برای کسر:");
          const amount = parseInt(input ?? "", 10);
          if (!Number.isNaN(amount) && amount !== 0) charge.mutate(amount);
        }}
      >
        شارژ کیف پول
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={setBalance.isPending}
        onClick={() => {
          const input = prompt("موجودی جدید (تومان):", String(user.wallet_balance));
          const balance = parseInt(input ?? "", 10);
          if (!Number.isNaN(balance) && balance >= 0) setBalance.mutate(balance);
        }}
      >
        تنظیم موجودی
      </Button>
      <Button
        size="sm"
        variant={user.is_blocked ? "secondary" : "destructive"}
        disabled={block.isPending}
        onClick={() => {
          if (confirm(user.is_blocked ? "رفع مسدودیت کاربر؟" : "مسدود کردن کاربر؟"))
            block.mutate();
        }}
      >
        {user.is_blocked ? "رفع مسدودی" : "مسدود"}
      </Button>
    </div>
  );
}

export function UsersPage() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const { data: users, isLoading } = useQuery({
    queryKey: ["users", search],
    queryFn: () => getUsers(search || undefined),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">کاربران</h1>

      <form
        className="flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(query.trim());
        }}
      >
        <Input
          placeholder="جستجو: شناسه تلگرام، نام کاربری یا نام…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button type="submit" size="icon" variant="secondary">
          <Search className="size-4" />
        </Button>
      </form>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : !users?.length ? (
        <p className="py-16 text-center text-sm text-muted-foreground">کاربری یافت نشد.</p>
      ) : (
        <div className="space-y-3">
          {users.map((user) => (
            <Card key={user.telegram_id}>
              <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="font-bold">{user.first_name}</p>
                    {user.username && (
                      <span className="text-sm text-muted-foreground" dir="ltr">
                        @{user.username}
                      </span>
                    )}
                    {user.is_blocked && <Badge variant="destructive">مسدود</Badge>}
                  </div>
                  <p className="text-xs text-muted-foreground" dir="ltr">
                    ID: {user.telegram_id}
                  </p>
                  <p className="text-sm">
                    موجودی: <span className="font-bold">{formatToman(user.wallet_balance)}</span>
                  </p>
                </div>
                <UserActions user={user} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
