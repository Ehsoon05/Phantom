"use client";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://webapi.phantomhubs.shop";

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

export interface Me {
  telegram_id: number;
  first_name: string;
  username: string | null;
  wallet_balance: number;
  referral_code: string | null;
  trial_claimed: boolean;
  accepted_rules: boolean;
  phone_verified: boolean;
}

export async function authenticate(initData: string, startParam?: string) {
  const data = await api<{ access_token: string; me: Me }>("/auth/telegram", {
    method: "POST",
    body: JSON.stringify({ init_data: initData, start_param: startParam ?? null }),
  });
  setToken(data.access_token);
  return data;
}

// --- Typed API surface -------------------------------------------------------

export interface Plan {
  id: number;
  volume_gb: number;
  volume_label: string;
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
  volume_label: string;
  category_key: string;
  price: number;
  original_price: number | null;
  discount_amount: number;
  coupon_code: string | null;
  service_name: string | null;
  purchased_at: string;
  sub_link: string | null;
  can_renew: boolean;
  renewal_price: number | null;
  renewed_at: string | null;
}

export interface PaymentMethods {
  crypto_coins: { key: string; label: string; coin: string; network: string }[];
  rial: {
    min_amount_toman: number;
    phone_required: boolean;
    source_card_required: boolean;
    phone_verified: boolean;
    verify_phone_url: string;
    payment_mode: "receipt_bot" | "direct_support";
  };
  hooshpay: {
    enabled: boolean;
    min_amount_toman: number;
    fee_mode: "seller" | "buyer" | "split";
    title: string;
    subtitle: string;
    amount_label: string;
    create_button: string;
    pay_button: string;
    preset_amounts: number[];
  };
}

export interface CryptoInvoice {
  id: number;
  coin: string;
  network: string;
  deposit_address: string;
  memo: string | null;
  expected_crypto: string;
  quoted_toman: number;
  status: string;
  created_at: string;
  expires_at: string | null;
}

export interface RialRequest {
  id: number;
  tracking_code: string;
  amount_toman: number;
  status: string;
  receipt_status: string | null;
  payment_mode: "receipt_bot" | "direct_support";
  support_handle: string;
  request_text: string;
  message_text: string | null;
  copy_text: string | null;
  send_url: string | null;
  destination_card: string | null;
  destination_holder: string | null;
  expires_at: string | null;
  receipt_bot_url: string | null;
  created_at: string;
}

export interface HooshPayInvoice {
  id: number;
  uid: string | null;
  order_id: string;
  amount_toman: number;
  payable_amount: number | null;
  merchant_credit: number | null;
  fee_amount: number | null;
  fee_percent: number | null;
  fee_mode: string;
  payment_url: string | null;
  card_number: string | null;
  card_holder: string | null;
  bank_name: string | null;
  status: string;
  tracking_code: string | null;
  created_at: string;
  expires_at: string | null;
  credited_at: string | null;
}

export interface Transaction {
  id: number;
  amount: number;
  type: string;
  description: string | null;
  created_at: string;
}

export const getPaymentMethods = () => api<PaymentMethods>("/wallet/methods");
export const getTransactions = () => api<Transaction[]>("/wallet/transactions");
export const getCryptoInvoices = () => api<CryptoInvoice[]>("/wallet/crypto/invoices");
export const getCryptoInvoice = (id: number) =>
  api<CryptoInvoice>(`/wallet/crypto/invoices/${id}`);
export const cancelCryptoInvoice = (id: number) =>
  api<CryptoInvoice>(`/wallet/crypto/invoices/${id}/cancel`, { method: "POST" });
export const createCryptoInvoice = (coinKey: string, amountToman: number) =>
  api<CryptoInvoice>("/wallet/crypto/invoices", {
    method: "POST",
    body: JSON.stringify({ coin_key: coinKey, amount_toman: amountToman }),
  });
export const createRialRequest = (input: {
  amount_toman: number;
  source_card?: string;
}) =>
  api<RialRequest>("/wallet/rial/requests", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const createHooshPayInvoice = (amountToman: number) =>
  api<HooshPayInvoice>("/wallet/hooshpay/invoices", {
    method: "POST",
    body: JSON.stringify({ amount_toman: amountToman }),
  });
export const getHooshPayInvoices = () => api<HooshPayInvoice[]>("/wallet/hooshpay/invoices");
export const verifyHooshPayInvoice = (id: number) =>
  api<HooshPayInvoice>(`/wallet/hooshpay/invoices/${id}/verify`, { method: "POST" });

export interface RialSummary {
  id: number;
  tracking_code: string;
  amount_toman: number;
  status: string;
  receipt_status?: string | null;
  payment_mode?: string;
  expires_at?: string | null;
  created_at: string;
}
export const getRialRequests = () => api<RialSummary[]>("/wallet/rial/requests");
export const cancelRialRequest = (id: number) =>
  api<{ id: number; status: string }>(`/wallet/rial/requests/${id}/cancel`, {
    method: "POST",
  });

export interface AppliedCoupon {
  code: string;
  discount_type: string;
  amount: number;
}

export interface ReferralRule {
  id: number;
  title: string;
  qualification_type: string;
  qualification_label: string;
  required_count: number;
  target_count: number;
  is_repeatable: boolean;
  reward_type: "wallet" | "service";
  wallet_amount: number | null;
  reward_text: string;
  qualified_count: number;
}

export interface Referrals {
  referral_code: string;
  referral_link: string;
  share_text: string;
  message_text: string;
  total_referrals: number;
  rules: ReferralRule[];
}

export const applyCoupon = (code: string) =>
  api<AppliedCoupon>("/shop/coupons/apply", {
    method: "POST",
    body: JSON.stringify({ code }),
  });

export const getMe = () => api<Me>("/auth/me");
export const getReferrals = () => api<Referrals>("/referrals");
export const getPlans = () => api<Category[]>("/shop/plans");
export const getPurchases = () => api<Purchase[]>("/shop/purchases");
export const buyPlan = (planId: number, idempotencyKey: string) =>
  api<Purchase>("/shop/purchases", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
    headers: { "Idempotency-Key": idempotencyKey },
  });
export const renewPurchase = (purchaseId: number) =>
  api<Purchase>(`/shop/purchases/${purchaseId}/renew`, {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });

export const formatToman = (value: number) =>
  `${value.toLocaleString("fa-IR")} تومان`;

// --- Deep links --------------------------------------------------------------

/** ton://transfer link that pre-fills address, exact nanoton amount, and memo —
 *  mirrors the bot's "Open TON wallet" button. Null for non-native-TON invoices. */
export function tonTransferLink(invoice: CryptoInvoice): string | null {
  if (invoice.coin !== "TON" || invoice.network !== "TON") return null;
  const nano = Math.round(parseFloat(invoice.expected_crypto) * 1e9);
  let url = `ton://transfer/${invoice.deposit_address}?amount=${nano}`;
  if (invoice.memo) url += `&text=${encodeURIComponent(invoice.memo)}`;
  return url;
}

export const happLink = (sub: string) => `happ://add/${sub}`;
export const v2rayNgLink = (sub: string) => `v2rayng://install-sub?url=${encodeURIComponent(sub)}`;
export const hiddifyLink = (sub: string) =>
  `hiddify://import/${encodeURIComponent(sub)}#PhantomHubs`;
export const v2boxLink = (sub: string) =>
  `v2box://install-sub?url=${encodeURIComponent(sub)}&name=${encodeURIComponent("PhantomHubs")}`;
export const streisandLink = () => "streisand://";
