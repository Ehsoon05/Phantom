"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let accessToken: string | null = null;

export function setToken(token: string) {
  accessToken = token;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function authenticate(initData: string, startParam?: string) {
  const data = await api<{ access_token: string }>("/auth/telegram", {
    method: "POST",
    body: JSON.stringify({ init_data: initData, start_param: startParam ?? null }),
  });
  setToken(data.access_token);
  return data;
}

// --- Typed API surface -------------------------------------------------------

export interface Me {
  telegram_id: number;
  first_name: string;
  username: string | null;
  wallet_balance: number;
  referral_code: string | null;
  trial_claimed: boolean;
  accepted_rules: boolean;
}

export interface Plan {
  id: number;
  volume_gb: number;
  category_key: string;
  title: string;
  price: number | null;
  final_price: number | null;
  discount_amount: number;
  emoji: string | null;
  style: string | null;
  display_order: number;
  in_stock: boolean;
}

export interface Category {
  key: string;
  title: string;
  emoji: string | null;
  display_order: number;
  plans: Plan[];
}

export interface Purchase {
  id: number;
  volume_gb: number;
  category_key: string;
  price: number;
  original_price: number | null;
  discount_amount: number;
  coupon_code: string | null;
  service_name: string | null;
  purchased_at: string;
  sub_link: string | null;
}

export const getMe = () => api<Me>("/auth/me");
export const getPlans = () => api<Category[]>("/shop/plans");
export const getPurchases = () => api<Purchase[]>("/shop/purchases");
export const buyPlan = (planId: number, idempotencyKey: string) =>
  api<Purchase>("/shop/purchases", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
    headers: { "Idempotency-Key": idempotencyKey },
  });

export const formatToman = (value: number) =>
  `${value.toLocaleString("fa-IR")} تومان`;
