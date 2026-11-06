import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import CountUp from "@/components/reactbits/CountUp";
import SpotlightCard from "@/components/reactbits/SpotlightCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatToman, getRevenueDaily, getSalesReport, getStats, getStock, hasPermission } from "@/lib/api";
import { formatTehranDateTime } from "@/lib/date";

function StatCard({
  title,
  value,
  suffix,
}: {
  title: string;
  value: number | undefined;
  suffix?: string;
}) {
  return (
    <SpotlightCard spotlightColor="rgba(80, 120, 255, 0.18)">
      <div className="space-y-1 p-4">
        <p className="text-xs text-muted-foreground">{title}</p>
        {value === undefined ? (
          <Skeleton className="h-7 w-24" />
        ) : (
          <p className="text-xl font-bold">
            <CountUp to={value} duration={0.45} separator="٬" locale="fa-IR" />
            {suffix ? ` ${suffix}` : ""}
          </p>
        )}
      </div>
    </SpotlightCard>
  );
}

export function DashboardPage() {
  const canReports = hasPermission("reports");
  const canInventory = hasPermission("inventory");
  const [reportDays, setReportDays] = useState(45);
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
  const { data: salesReport } = useQuery({
    queryKey: ["sales-report", reportDays],
    queryFn: () => getSalesReport(reportDays, 100),
    enabled: canReports,
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
            value={stats?.total_wallet_balance}
            suffix="تومان"
          />
          <StatCard title="حجم فروخته‌شده" value={stats?.total_gb_purchased} suffix="GB" />
          <StatCard title="مجموع فروش" value={stats?.total_spent} suffix="تومان" />
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

      {canReports && (
        <Card>
          <CardContent className="p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">گزارش کامل فروش</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  تفکیک خرید، تمدید، انبار، ساخت از پنل، دسته و سرویس
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {[7, 30, 45, 90].map((days) => (
                  <Button
                    key={days}
                    size="sm"
                    variant={reportDays === days ? "default" : "secondary"}
                    onClick={() => setReportDays(days)}
                  >
                    {days} روز
                  </Button>
                ))}
              </div>
            </div>
            {salesReport === undefined ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <div className="space-y-5">
                <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
                  <div className="rounded-lg bg-muted p-3">
                    <p className="text-xs text-muted-foreground">کل تراکنش</p>
                    <p className="mt-1 font-bold">{salesReport.summary.total_transactions}</p>
                  </div>
                  <div className="rounded-lg bg-muted p-3">
                    <p className="text-xs text-muted-foreground">خرید جدید</p>
                    <p className="mt-1 font-bold">{salesReport.summary.sales}</p>
                  </div>
                  <div className="rounded-lg bg-muted p-3">
                    <p className="text-xs text-muted-foreground">تمدید</p>
                    <p className="mt-1 font-bold">{salesReport.summary.renewals}</p>
                  </div>
                  <div className="rounded-lg bg-muted p-3">
                    <p className="text-xs text-muted-foreground">انبار</p>
                    <p className="mt-1 font-bold">{salesReport.summary.inventory}</p>
                  </div>
                  <div className="rounded-lg bg-muted p-3">
                    <p className="text-xs text-muted-foreground">پنل</p>
                    <p className="mt-1 font-bold">{salesReport.summary.panel}</p>
                  </div>
                  <div className="rounded-lg bg-muted p-3">
                    <p className="text-xs text-muted-foreground">درآمد</p>
                    <p className="mt-1 font-bold">{formatToman(salesReport.summary.revenue_toman)}</p>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <BreakdownTable title="تفکیک سرویس‌ها" rows={salesReport.by_service} />
                  <BreakdownTable title="تفکیک دسته‌ها" rows={salesReport.by_category} />
                </div>

                <div className="max-h-80 overflow-auto">
                  <p className="mb-3 text-sm font-semibold">روزهای بازه انتخابی</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-right text-xs text-muted-foreground">
                        <th className="pb-2 font-medium">تاریخ</th>
                        <th className="pb-2 font-medium">فروش</th>
                        <th className="pb-2 font-medium">تمدید</th>
                        <th className="pb-2 font-medium">انبار</th>
                        <th className="pb-2 font-medium">پنل</th>
                        <th className="pb-2 font-medium">درآمد</th>
                      </tr>
                    </thead>
                    <tbody>
                      {salesReport.daily.map((row) => (
                        <tr key={row.date} className="border-b last:border-0">
                          <td className="py-2">{row.date}</td>
                          <td className="py-2">{row.sales}</td>
                          <td className="py-2">{row.renewals}</td>
                          <td className="py-2">{row.inventory}</td>
                          <td className="py-2">{row.panel}</td>
                          <td className="py-2">{formatToman(row.revenue_toman)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="max-h-96 overflow-auto">
                  <p className="mb-3 text-sm font-semibold">آخرین فروش‌ها و تمدیدها</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-right text-xs text-muted-foreground">
                        <th className="pb-2 font-medium">زمان</th>
                        <th className="pb-2 font-medium">کاربر</th>
                        <th className="pb-2 font-medium">سرویس</th>
                        <th className="pb-2 font-medium">دسته</th>
                        <th className="pb-2 font-medium">نوع</th>
                        <th className="pb-2 font-medium">تامین</th>
                        <th className="pb-2 font-medium">مبلغ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {salesReport.recent.map((row) => (
                        <tr key={row.id} className="border-b last:border-0">
                          <td className="py-2">{formatTehranDateTime(row.purchased_at)}</td>
                          <td className="py-2" dir="ltr">{row.user_id}</td>
                          <td className="py-2">{row.service_name ?? `${row.volume_gb} GB`}</td>
                          <td className="py-2 text-muted-foreground">{row.category_key}</td>
                          <td className="py-2">{row.kind === "renewal" ? "تمدید" : "خرید"}</td>
                          <td className="py-2">{row.provision_source === "panel" ? "پنل" : "انبار"}</td>
                          <td className="py-2">{formatToman(row.price)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function BreakdownTable({
  title,
  rows,
}: {
  title: string;
  rows: { key: string; count: number; revenue_toman: number }[];
}) {
  return (
    <div className="rounded-lg border p-3">
      <p className="mb-3 text-sm font-semibold">{title}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-right text-xs text-muted-foreground">
            <th className="pb-2 font-medium">عنوان</th>
            <th className="pb-2 font-medium">تعداد</th>
            <th className="pb-2 font-medium">درآمد</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 10).map((row) => (
            <tr key={row.key} className="border-b last:border-0">
              <td className="py-2">{row.key}</td>
              <td className="py-2">{row.count}</td>
              <td className="py-2">{formatToman(row.revenue_toman)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
