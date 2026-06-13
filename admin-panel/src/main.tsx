import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/layout";
import { getToken } from "@/lib/api";
import { AdminsPage } from "@/pages/admins";
import { BroadcastPage } from "@/pages/broadcast";
import { CatalogPage } from "@/pages/catalog";
import { DashboardPage } from "@/pages/dashboard";
import { LoginPage } from "@/pages/login";
import { PaymentsPage } from "@/pages/payments";
import { PromotionsPage } from "@/pages/promotions";
import { SettingsPage } from "@/pages/settings";
import { ShopPage } from "@/pages/shop";
import { UsersPage } from "@/pages/users";

import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 15_000 } },
});

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="payments" element={<PaymentsPage />} />
            <Route path="catalog" element={<CatalogPage />} />
            <Route path="promotions" element={<PromotionsPage />} />
            <Route path="shop" element={<ShopPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="broadcast" element={<BroadcastPage />} />
            <Route path="admins" element={<AdminsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
