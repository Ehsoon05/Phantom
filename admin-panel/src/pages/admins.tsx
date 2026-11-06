import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { addAdmin, listAdmins, removeAdmin, setAdminPermissions } from "@/lib/admin-api";

const PERMISSIONS = ["inventory", "prices", "users", "reports", "coupons", "shop"];

export function AdminsPage() {
  const qc = useQueryClient();
  const { data: admins, isLoading } = useQuery({ queryKey: ["admin-admins"], queryFn: listAdmins });
  const inv = () => qc.invalidateQueries({ queryKey: ["admin-admins"] });
  const [tid, setTid] = useState("");
  const [perms, setPerms] = useState<string[]>(["reports"]);
  const [err, setErr] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () => addAdmin(parseInt(tid, 10), perms.join(",")),
    onSuccess: () => { setTid(""); setPerms(["reports"]); setErr(null); inv(); },
    onError: (e) => setErr(e instanceof ApiError ? e.message : "خطا"),
  });
  const setPerm = useMutation({ mutationFn: (p: { id: number; perms: string }) => setAdminPermissions(p.id, p.perms), onSuccess: inv });
  const remove = useMutation({ mutationFn: (id: number) => removeAdmin(id), onSuccess: inv });

  const togglePerm = (p: string) => setPerms((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]));

  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">مدیران</h1>
      <Card><CardContent className="space-y-3 p-4">
        <p className="text-sm font-semibold">افزودن مدیر</p>
        <Input placeholder="شناسه تلگرام" dir="ltr" inputMode="numeric" value={tid} onChange={(e) => setTid(e.target.value)} />
        <div className="flex flex-wrap gap-3">
          {PERMISSIONS.map((p) => (
            <label key={p} className="flex items-center gap-1 text-sm">
              <input type="checkbox" checked={perms.includes(p)} onChange={() => togglePerm(p)} /> {p}
            </label>
          ))}
        </div>
        {err && <p className="text-sm text-destructive">{err}</p>}
        <Button disabled={!tid || add.isPending} onClick={() => add.mutate()}>افزودن</Button>
      </CardContent></Card>

      <div className="space-y-2">
        {admins?.map((a) => (
          <Card key={a.telegram_id}><CardContent className="flex flex-wrap items-center justify-between gap-2 p-3">
            <div>
              <span className="font-bold" dir="ltr">{a.telegram_id}</span>{" "}
              {a.is_owner && <Badge>مالک</Badge>}{" "}
              {!a.is_active && <Badge variant="destructive">غیرفعال</Badge>}
              <p className="text-xs text-muted-foreground">{a.permissions || "—"}</p>
            </div>
            {!a.is_owner && (
              <div className="flex gap-1">
                <Button size="sm" variant="outline" onClick={() => { const p = prompt("مجوزها (با کاما):", a.permissions); if (p != null) setPerm.mutate({ id: a.telegram_id, perms: p }); }}>مجوزها</Button>
                <Button size="sm" variant="destructive" onClick={() => { if (confirm("حذف مدیر؟")) remove.mutate(a.telegram_id); }}>حذف</Button>
              </div>
            )}
          </CardContent></Card>
        ))}
      </div>
    </div>
  );
}
