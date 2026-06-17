const API_BASE =
  import.meta.env.VITE_API_URL ?? "https://webapi.phantomhubs.shop";

const TOKEN_KEY = "phantom_admin_token";
const PERMS_KEY = "phantom_admin_perms";

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getPermissions(): { perms: string[]; isOwner: boolean } {
  try {
    return JSON.parse(sessionStorage.getItem(PERMS_KEY) ?? "");
  } catch {
    return { perms: [], isOwner: false };
  }
}

export function hasPermission(permission: string) {
  const { perms, isOwner } = getPermissions();
  return isOwner || perms.includes("all") || perms.includes(permission);
}

export function logout() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(PERMS_KEY);
  window.location.href = "/login";
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (res.status === 401 && path !== "/admin/auth/login") {
    logout();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function login(telegramId: number, password: string) {
  const data = await api<{ access_token: string; permissions: string; is_owner: boolean }>(
    "/admin/auth/login",
    { method: "POST", body: JSON.stringify({ telegram_id: telegramId, password }) }
  );
  sessionStorage.setItem(TOKEN_KEY, data.access_token);
  sessionStorage.setItem(
    PERMS_KEY,
    JSON.stringify({
      perms: data.permissions.split(",").map((p) => p.trim()).filter(Boolean),
      isOwner: data.is_owner,
    })
  );
  return data;
}

// --- Types -------------------------------------------------------------------

export interface Stats {
  total_users: number;
  new_users_today: number;
  total_wallet_balance: number;
  total_gb_purchased: number;
  total_spent: number;
}

export interface RevenuePoint {
  date: string;
  revenue_toman: number;
  purchases: number;
}

export interface SalesDailyPoint {
  date: string;
  revenue_toman: number;
  sales: number;
  renewals: number;
  inventory: number;
  panel: number;
}

export interface StockRow {
  category_key: string;
  volume_gb: number;
  title: string;
  available: number;
}

export interface AdminUser {
  telegram_id: number;
  first_name: string;
  username: string | null;
  wallet_balance: number;
  is_blocked: boolean;
  referral_code: string | null;
  created_at: string | null;
}

export interface RialRequest {
  id: number;
  tracking_code: string;
  user_id: number;
  amount_toman: number;
  phone_number: string | null;
  source_card: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CryptoInvoice {
  id: number;
  user_id: number;
  coin: string;
  network: string;
  quoted_toman: number;
  expected_crypto: string;
  received_crypto: string | null;
  status: string;
  tx_hash: string | null;
  created_at: string;
  credited_at: string | null;
}

export const getStats = () => api<Stats>("/admin/stats");
export const getRevenueDaily = (days = 30) =>
  api<RevenuePoint[]>(`/admin/stats/revenue-daily?days=${days}`);
export const getSalesDaily = (days = 45) =>
  api<SalesDailyPoint[]>(`/admin/stats/sales-daily?days=${days}`);
export const getStock = () => api<StockRow[]>("/admin/stats/stock");
export const getUsers = (q?: string, limit = 25, offset = 0) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q) params.set("q", q);
  return api<AdminUser[]>(`/admin/users?${params.toString()}`);
};
export const chargeUser = (telegramId: number, amount: number) =>
  api<AdminUser>(`/admin/users/${telegramId}/charge`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
export const setUserBalance = (telegramId: number, balance: number) =>
  api<AdminUser>(`/admin/users/${telegramId}/balance`, {
    method: "POST",
    body: JSON.stringify({ balance }),
  });
export const toggleBlockUser = (telegramId: number) =>
  api<AdminUser>(`/admin/users/${telegramId}/block`, { method: "POST" });
export const getRialRequests = (status = "pending") =>
  api<RialRequest[]>(`/admin/payments/rial?status=${status}`);
export const decideRial = (id: number, approve: boolean) =>
  api<RialRequest>(`/admin/payments/rial/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ approve }),
  });
export const getCryptoLedger = () => api<CryptoInvoice[]>("/admin/payments/crypto");

export const formatToman = (value: number) => `${value.toLocaleString("fa-IR")} تومان`;
