import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/layout";
import { getToken } from "@/lib/api";

import "./index.css";

const AdminsPage = lazy(() => import("@/pages/admins").then((module) => ({ default: module.AdminsPage })));
const BroadcastPage = lazy(() => import("@/pages/broadcast").then((module) => ({ default: module.BroadcastPage })));
const CatalogPage = lazy(() => import("@/pages/catalog").then((module) => ({ default: module.CatalogPage })));
const DashboardPage = lazy(() => import("@/pages/dashboard").then((module) => ({ default: module.DashboardPage })));
const LoginPage = lazy(() => import("@/pages/login").then((module) => ({ default: module.LoginPage })));
const PaymentsPage = lazy(() => import("@/pages/payments").then((module) => ({ default: module.PaymentsPage })));
const PromotionsPage = lazy(() => import("@/pages/promotions").then((module) => ({ default: module.PromotionsPage })));
const SettingsPage = lazy(() => import("@/pages/settings").then((module) => ({ default: module.SettingsPage })));
const ShopPage = lazy(() => import("@/pages/shop").then((module) => ({ default: module.ShopPage })));
const SellersPage = lazy(() => import("@/pages/sellers").then((module) => ({ default: module.SellersPage })));
const UsersPage = lazy(() => import("@/pages/users").then((module) => ({ default: module.UsersPage })));

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
        <Suspense fallback={<div className="grid min-h-dvh place-items-center text-sm text-muted-foreground">در حال بارگذاری…</div>}>
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
              <Route path="sellers" element={<SellersPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
