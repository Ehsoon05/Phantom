import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, login } from "@/lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const [telegramId, setTelegramId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login(parseInt(telegramId, 10) || 0, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? "شناسه یا رمز عبور اشتباه است" : "خطا در اتصال به سرور");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardContent className="p-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1 text-center">
              <p className="text-3xl">👻</p>
              <h1 className="text-lg font-bold">پنل مدیریت فانتوم</h1>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">شناسه تلگرام</label>
              <Input
                dir="ltr"
                inputMode="numeric"
                value={telegramId}
                onChange={(e) => setTelegramId(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">رمز عبور</label>
              <Input
                dir="ltr"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "در حال ورود…" : "ورود"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
