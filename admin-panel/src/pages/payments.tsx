import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  decideRial,
  formatToman,
  getCryptoLedger,
  getRialRequests,
  type RialRequest,
} from "@/lib/api";
import { formatTehranDateTime } from "@/lib/date";

const CRYPTO_STATUS_TONE: Record<string, "default" | "secondary" | "destructive"> = {
  credited: "default",
  pending: "secondary",
  paid: "secondary",
  confirmed: "secondary",
  expired: "destructive",
  underpaid: "destructive",
  error: "destructive",
};

function RialCard({ request }: { request: RialRequest }) {
  const queryClient = useQueryClient();
  const decide = useMutation({
    mutationFn: ({ approve, reason }: { approve: boolean; reason?: string }) => decideRial(request.id, approve, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rial-requests"] });
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1 text-sm">
          <p className="font-bold">{formatToman(request.amount_toman)}</p>
          <p className="text-xs text-muted-foreground" dir="ltr">
            کد پیگیری: {request.tracking_code}
          </p>
          <p className="text-xs text-muted-foreground" dir="ltr">
            کاربر: {request.user_id} · کارت: {request.source_card}
            {request.phone_number ? ` · ${request.phone_number}` : ""}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatTehranDateTime(request.created_at)}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            disabled={decide.isPending}
            onClick={() => {
              if (confirm(`تایید و شارژ ${formatToman(request.amount_toman)}؟`))
                decide.mutate({ approve: true });
            }}
          >
            ✅ تایید و شارژ
          </Button>
          <Button
            size="sm"
            variant="destructive"
            disabled={decide.isPending}
            onClick={() => {
              const reason = prompt("دلیل رد را بنویسید. اگر لازم نیست خالی بگذارید:") ?? "";
              if (confirm("رد درخواست؟")) decide.mutate({ approve: false, reason: reason.trim() || undefined });
            }}
          >
            رد
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function RialQueue() {
  const { data: requests, isLoading } = useQuery({
    queryKey: ["rial-requests"],
    queryFn: () => getRialRequests("pending"),
    refetchInterval: 30_000,
  });
  if (isLoading) return <Skeleton className="h-32 w-full rounded-xl" />;
  if (!requests?.length)
    return (
      <p className="py-16 text-center text-sm text-muted-foreground">
        درخواست در انتظاری وجود ندارد. 🎉
      </p>
    );
  return (
    <div className="space-y-3">
      {requests.map((request) => (
        <RialCard key={request.id} request={request} />
      ))}
    </div>
  );
}

function CryptoLedger() {
  const { data: invoices, isLoading } = useQuery({
    queryKey: ["crypto-ledger"],
    queryFn: getCryptoLedger,
  });
  if (isLoading) return <Skeleton className="h-32 w-full rounded-xl" />;
  if (!invoices?.length)
    return (
      <p className="py-16 text-center text-sm text-muted-foreground">فاکتوری ثبت نشده است.</p>
    );
  return (
    <Card>
      <CardContent className="overflow-x-auto p-4">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b text-right text-xs text-muted-foreground">
              <th className="pb-2 font-medium">کاربر</th>
              <th className="pb-2 font-medium">ارز</th>
              <th className="pb-2 font-medium">مبلغ</th>
              <th className="pb-2 font-medium">وضعیت</th>
              <th className="pb-2 font-medium">تراکنش</th>
              <th className="pb-2 font-medium">تاریخ</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice.id} className="border-b last:border-0">
                <td className="py-2" dir="ltr">
                  {invoice.user_id}
                </td>
                <td className="py-2">
                  {invoice.coin} · {invoice.network}
                </td>
                <td className="py-2">{formatToman(invoice.quoted_toman)}</td>
                <td className="py-2">
                  <Badge variant={CRYPTO_STATUS_TONE[invoice.status] ?? "secondary"}>
                    {invoice.status}
                  </Badge>
                </td>
                <td className="max-w-32 truncate py-2 text-xs" dir="ltr">
                  {invoice.tx_hash ?? "—"}
                </td>
                <td className="py-2 text-xs text-muted-foreground">
                  {formatTehranDateTime(invoice.created_at, false)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export function PaymentsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">پرداخت‌ها</h1>
      <Tabs defaultValue="rial">
        <TabsList>
          <TabsTrigger value="rial">🏦 صف ریالی</TabsTrigger>
          <TabsTrigger value="crypto">💎 کریپتو</TabsTrigger>
        </TabsList>
        <TabsContent value="rial" className="pt-4">
          <RialQueue />
        </TabsContent>
        <TabsContent value="crypto" className="pt-4">
          <CryptoLedger />
        </TabsContent>
      </Tabs>
    </div>
  );
}
