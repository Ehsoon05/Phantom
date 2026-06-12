import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatToman, getRevenueDaily, getStats, getStock, hasPermission } from "@/lib/api";

function StatCard({ title, value }: { title: string; value: string | number | undefined }) {
  return (
    <Card>
      <CardContent className="space-y-1 p-4">
        <p className="text-xs text-muted-foreground">{title}</p>
        {value === undefined ? (
          <Skeleton className="h-7 w-24" />
        ) : (
          <p className="text-xl font-bold">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const canReports = hasPermission("reports");
  const canInventory = hasPermission("inventory");
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    enabled: canReports,
  });
  const { data: revenue } = useQuery({
    queryKey: ["revenue-daily"],
    queryFn: () => getRevenueDaily(30),
    enabled: canReports,
  });
  const { data: stock } = useQuery({
    queryKey: ["stock"],
    queryFn: getStock,
    enabled: canInventory,
  });

  const lowStock = stock?.filter((row) => row.available <= 3) ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">داشبورد</h1>

      {canReports && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatCard title="کل کاربران" value={stats?.total_users} />
          <StatCard title="کاربر جدید امروز" value={stats?.new_users_today} />
          <StatCard
            title="مجموع موجودی کیف پول‌ها"
            value={stats ? formatToman(stats.total_wallet_balance) : undefined}
          />
          <StatCard
            title="حجم فروخته‌شده"
            value={stats ? `${stats.total_gb_purchased} GB` : undefined}
          />
          <StatCard
            title="مجموع فروش"
            value={stats ? formatToman(stats.total_spent) : undefined}
          />
        </div>
      )}

      {canReports && (
        <Card>
          <CardContent className="p-4">
            <p className="mb-4 text-sm font-semibold">درآمد ۳۰ روز اخیر</p>
            {revenue === undefined ? (
              <Skeleton className="h-64 w-full" />
            ) : revenue.length === 0 ? (
              <p className="py-16 text-center text-sm text-muted-foreground">
                فروشی در این بازه ثبت نشده است.
              </p>
            ) : (
              <div className="h-64" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={revenue}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="date" fontSize={11} tickFormatter={(d) => d.slice(5)} />
                    <YAxis
                      fontSize={11}
                      tickFormatter={(v: number) => (v >= 1e6 ? `${v / 1e6}M` : `${v / 1e3}k`)}
                    />
                    <Tooltip
                      formatter={(value) => [formatToman(Number(value)), "درآمد"]}
                    />
                    <Bar dataKey="revenue_toman" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {canInventory && (
        <Card>
          <CardContent className="p-4">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm font-semibold">موجودی انبار</p>
              {lowStock.length > 0 && (
                <Badge variant="destructive">{lowStock.length} مورد رو به اتمام</Badge>
              )}
            </div>
            {stock === undefined ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-right text-xs text-muted-foreground">
                    <th className="pb-2 font-medium">پلن</th>
                    <th className="pb-2 font-medium">دسته</th>
                    <th className="pb-2 font-medium">حجم</th>
                    <th className="pb-2 font-medium">موجودی</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.map((row) => (
                    <tr key={`${row.category_key}-${row.volume_gb}`} className="border-b last:border-0">
                      <td className="py-2">{row.title}</td>
                      <td className="py-2 text-muted-foreground">{row.category_key}</td>
                      <td className="py-2">{row.volume_gb} GB</td>
                      <td className="py-2">
                        <Badge variant={row.available <= 3 ? "destructive" : "secondary"}>
                          {row.available}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
