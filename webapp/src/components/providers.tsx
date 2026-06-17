"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState } from "react";

import { authenticate } from "@/lib/api";
import { applyTelegramTheme, getWebApp } from "@/lib/telegram";

type AuthState = "loading" | "ready" | "outside-telegram" | "error";

const AuthContext = createContext<AuthState>("loading");
export const useAuthState = () => useContext(AuthContext);

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

export function Providers({ children }: { children: React.ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>("loading");

  useEffect(() => {
    const tg = getWebApp();
    if (!tg || !tg.initData) {
      setAuthState("outside-telegram");
      return;
    }
    tg.ready();
    tg.expand();
    applyTelegramTheme(tg);
    tg.onEvent("themeChanged", () => applyTelegramTheme(tg));
    authenticate(tg.initData, tg.initDataUnsafe.start_param)
      .then((auth) => {
        queryClient.setQueryData(["me"], auth.me);
        setAuthState("ready");
      })
      .catch(() => setAuthState("error"));
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={authState}>{children}</AuthContext.Provider>
    </QueryClientProvider>
  );
}
