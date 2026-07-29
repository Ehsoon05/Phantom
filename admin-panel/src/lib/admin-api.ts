import { api, getToken, logout } from "./api";

const SELLER_API_BASE =
  import.meta.env.VITE_SELLER_API_URL ?? "https://sellers.phantomhubs.shop";

async function sellerApi<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(`${SELLER_API_BASE}/api/admin${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (response.status === 401) logout();
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // Keep HTTP status text.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export interface SellerAccount {
  id: number;
  username: string;
  display_name: string;
  wallet_balance: number;
  allow_negative_balance: boolean;
  is_active: boolean;
  service_count?: number;
  created_at: string;
}

export interface SellerPanelOption {
  key: string;
  title: string;
  panel_type: string;
  hwid_limit: number | null;
}

export interface SellerOffer {
  id: number;
  seller_id: number;
  title: string;
  panel_key: string;
  price_toman: number;
  volume_gb: number;
  lock_volume: boolean;
  default_duration_days: number;
  allowed_time_modes: string[];
  default_time_mode: string;
  lock_time: boolean;
  lock_time_mode: boolean;
  lock_duration: boolean;
  name_prefix: string;
  panel_hwid_limit: number | null;
  subscription_device_limit: number;
  profile_title: string | null;
  support_url: string | null;
  show_header: boolean;
  show_config_preview: boolean;
  info_proxies_enabled: boolean;
  is_active: boolean;
}

export interface SellerSummary {
  sellers: number;
  active_sellers: number;
  services: number;
  revenue: number;
}

export interface SellerBuiltService {
  id: number;
  offer_id: number;
  panel_key: string;
  panel_username: string;
  public_url: string;
  volume_gb: number;
  duration_days: number;
  time_mode: string;
  price_toman: number;
  status: string;
  created_at: string;
}

export const getSellerSummary = () => sellerApi<SellerSummary>("/summary");
export const listSellers = (q = "") =>
  sellerApi<SellerAccount[]>(`/sellers${q ? `?q=${encodeURIComponent(q)}` : ""}`);
export const createSeller = (body: {
  username: string;
  display_name: string;
  password: string;
  initial_balance: number;
  allow_negative_balance: boolean;
}) => sellerApi<SellerAccount>("/sellers", { method: "POST", body: JSON.stringify(body) });
export const updateSeller = (id: number, body: Record<string, unknown>) =>
  sellerApi<SellerAccount>(`/sellers/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const adjustSellerBalance = (id: number, amount: number, description: string) =>
  sellerApi<SellerAccount>(`/sellers/${id}/balance`, {
    method: "POST",
    body: JSON.stringify({ amount, description }),
  });
export const listSellerPanels = () => sellerApi<SellerPanelOption[]>("/panels");
export const listSellerOffers = (sellerId: number) =>
  sellerApi<SellerOffer[]>(`/sellers/${sellerId}/offers`);
export const createSellerOffer = (sellerId: number, body: Record<string, unknown>) =>
  sellerApi<SellerOffer>(`/sellers/${sellerId}/offers`, {
    method: "POST",
    body: JSON.stringify(body),
  });
export const updateSellerOffer = (offerId: number, body: Record<string, unknown>) =>
  sellerApi<SellerOffer>(`/offers/${offerId}`, { method: "PUT", body: JSON.stringify(body) });
export const deleteSellerOffer = (offerId: number) =>
  sellerApi<{ deleted: boolean; deactivated: boolean }>(`/offers/${offerId}`, {
    method: "DELETE",
  });
export const listSellerBuiltServices = (sellerId: number) =>
  sellerApi<SellerBuiltService[]>(`/services?seller_id=${sellerId}`);
export const deleteSellerBuiltService = (serviceId: number) =>
  sellerApi<{ deleted: boolean }>(`/services/${serviceId}`, { method: "DELETE" });

// --- Catalog: plans / categories / inventory --------------------------------

export interface Plan {
  id: number;
  volume_gb: number;
  category_key: string;
  title: string;
  price: number | null;
  emoji: string | null;
  style: string | null;
  display_order: number;
  duration_days: number;
  provision_volume_gb: number | null;
  provision_duration_days: number | null;
  provision_time_mode: string;
  subscription_device_limit: number;
  show_subscription_configs: boolean;
  name_prefix: string | null;
  provision_mode: string;
  provision_panel_key: string | null;
  provision_enabled: boolean;
  renew_enabled: boolean;
  is_active: boolean;
  stock: number | null;
}

export interface Category {
  id: number;
  key: string;
  title: string;
  emoji: string | null;
  style: string | null;
  provision_panel_key: string | null;
  provision_enabled: boolean;
  display_order: number;
  is_active: boolean;
}

export const listPlans = () => api<Plan[]>("/admin/plans");
export const upsertPlan = (body: {
  volume_gb: number;
  title: string;
  price: number | null;
  category_key: string;
  emoji?: string | null;
}) => api<Plan>("/admin/plans", { method: "POST", body: JSON.stringify(body) });
export const updatePlan = (id: number, body: Record<string, unknown>) =>
  api<Plan>(`/admin/plans/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const setPlanPrice = (id: number, price: number) =>
  api<Plan>(`/admin/plans/${id}/price`, { method: "POST", body: JSON.stringify({ price }) });
export const deletePlan = (id: number) =>
  api<{ deleted: boolean }>(`/admin/plans/${id}`, { method: "DELETE" });

export const listCategories = () => api<Category[]>("/admin/categories");
export const upsertCategory = (key: string, title?: string) =>
  api<Category>("/admin/categories", { method: "POST", body: JSON.stringify({ key, title }) });
export const updateCategory = (key: string, body: Record<string, unknown>) =>
  api<Category>(`/admin/categories/${encodeURIComponent(key)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
export const deleteCategory = (key: string) =>
  api<{ deleted: boolean }>(`/admin/categories/${encodeURIComponent(key)}`, { method: "DELETE" });

export interface StockRow {
  plan_id: number;
  category_key: string;
  volume_gb: number;
  title: string;
  available: number;
}
export const getInventoryStock = () => api<StockRow[]>("/admin/inventory/stock");
export const addConfigs = (
  plan_id: number,
  volume_gb: number,
  category_key: string,
  links: string[],
) =>
  api<{ added: number }>("/admin/inventory/configs", {
    method: "POST",
    body: JSON.stringify({ plan_id, volume_gb, category_key, links }),
  });

export interface InventoryConfig {
  id: number;
  plan_id: number | null;
  volume_gb: number;
  category_key: string;
  name: string;
  sub_link: string;
  public_sub_token: string | null;
  subscription_device_limit: number | null;
  created_at: string;
}
export const listInventoryConfigs = (categoryKey?: string, volumeGb?: number, q?: string) => {
  const params = new URLSearchParams();
  if (categoryKey) params.set("category_key", categoryKey);
  if (volumeGb) params.set("volume_gb", String(volumeGb));
  if (q) params.set("q", q);
  const query = params.toString();
  return api<InventoryConfig[]>(`/admin/inventory/configs${query ? `?${query}` : ""}`);
};
export const replaceInventoryConfig = (id: number, subLink: string) =>
  api<InventoryConfig>(`/admin/inventory/configs/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ sub_link: subLink }),
  });
export const updateInventoryConfigDeviceLimit = (id: number, subscriptionDeviceLimit: number) =>
  api<InventoryConfig>(`/admin/inventory/configs/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ subscription_device_limit: subscriptionDeviceLimit }),
  });
export const deleteInventoryConfig = (id: number) =>
  api<{ deleted: boolean }>(`/admin/inventory/configs/${id}`, { method: "DELETE" });

export interface ProvisionPanel {
  key: string;
  title: string;
  panel_type: string;
  base_url: string;
  group_ids: number[];
  inbounds: Record<string, string[]>;
  protocols: string[];
  hwid_limit: number | null;
  is_enabled: boolean;
}

export const listProvisionPanels = () => api<ProvisionPanel[]>("/admin/provision/panels");

// --- Coupons ----------------------------------------------------------------

export interface Coupon {
  id: number;
  code: string;
  discount_type: string;
  amount: number;
  applies_to_all: boolean;
  is_active: boolean;
  target_user_count: number;
}

export const listCoupons = () => api<Coupon[]>("/admin/coupons");
export const createCoupon = (body: {
  code: string;
  discount_type: string;
  amount: number;
  target_user_ids: number[] | null;
}) => api<Coupon>("/admin/coupons", { method: "POST", body: JSON.stringify(body) });
export const updateCoupon = (
  code: string,
  body: { discount_type: string; amount: number; target_user_ids: number[] | null }
) => api<Coupon>(`/admin/coupons/${encodeURIComponent(code)}`, { method: "PUT", body: JSON.stringify(body) });
export const deactivateCoupon = (code: string) =>
  api<Coupon>(`/admin/coupons/${encodeURIComponent(code)}/deactivate`, { method: "POST" });
export const deleteCoupon = (code: string) =>
  api<{ deleted: boolean }>(`/admin/coupons/${encodeURIComponent(code)}`, { method: "DELETE" });

// --- Referral rules ---------------------------------------------------------

export interface Rule {
  id: number;
  title: string;
  qualification_type: string;
  required_count: number;
  is_repeatable: boolean;
  reward_type: string;
  wallet_amount: number | null;
  shop_plan_id: number | null;
  is_active: boolean;
}

export interface ReferralCommissionSettings {
  enabled: boolean;
  percent: number;
}

export const getReferralCommission = () => api<ReferralCommissionSettings>("/admin/referrals/commission");
export const setReferralCommission = (body: ReferralCommissionSettings) =>
  api<ReferralCommissionSettings>("/admin/referrals/commission", {
    method: "PUT",
    body: JSON.stringify(body),
  });
export const listRules = () => api<Rule[]>("/admin/referrals/rules");
export const createRule = (body: {
  title: string;
  qualification_type: string;
  required_count: number;
  is_repeatable: boolean;
  reward_type: string;
  wallet_amount: number | null;
  shop_plan_id: number | null;
}) => api<Rule>("/admin/referrals/rules", { method: "POST", body: JSON.stringify(body) });
export const toggleRule = (id: number) =>
  api<Rule>(`/admin/referrals/rules/${id}/toggle`, { method: "POST" });
export const deleteRule = (id: number) =>
  api<{ deleted: boolean }>(`/admin/referrals/rules/${id}`, { method: "DELETE" });
export const recalcReferrals = () =>
  api<{ grants: number }>("/admin/referrals/recalculate", { method: "POST" });

// --- Shop customization -----------------------------------------------------

export interface ShopMessage {
  key: string;
  text: string;
  parse_mode: string;
  is_active: boolean;
  response_button_type: string;
  response_button_text: string | null;
  response_button_url: string | null;
  response_button_style: string | null;
  response_button_premium_emoji_id: string | null;
  response_button_source_id: number | null;
}
export interface ShopMessageButton {
  id: number;
  message_key: string;
  button_type: string;
  text: string;
  payload: string | null;
  style: string | null;
  premium_emoji_id: string | null;
  source_button_id: number | null;
  row: number;
  col: number;
  is_enabled: boolean;
}
export interface ShopButton {
  id: number;
  menu: string;
  action: string;
  text: string;
  emoji: string | null;
  style: string | null;
  row: number;
  col: number;
  is_enabled: boolean;
}
export const listMessages = () => api<ShopMessage[]>("/admin/shop/messages");
export const updateMessage = (key: string, text: string, parse_mode: string) =>
  api<ShopMessage>(`/admin/shop/messages/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ text, parse_mode }),
  });
export const listMessageButtons = (messageKey?: string) =>
  api<ShopMessageButton[]>(`/admin/shop/message-buttons${messageKey ? `?message_key=${encodeURIComponent(messageKey)}` : ""}`);
export const createMessageButton = (body: {
  message_key: string;
  button_type: string;
  text: string;
  payload?: string | null;
  style?: string | null;
  premium_emoji_id?: string | null;
  source_button_id?: number | null;
  row?: number;
  col?: number;
}) => api<ShopMessageButton>("/admin/shop/message-buttons", { method: "POST", body: JSON.stringify(body) });
export const updateMessageButton = (id: number, body: Partial<Omit<ShopMessageButton, "id" | "message_key">>) =>
  api<ShopMessageButton>(`/admin/shop/message-buttons/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
export const deleteMessageButton = (id: number) =>
  api<{ deleted: boolean }>(`/admin/shop/message-buttons/${id}`, { method: "DELETE" });
export const listButtons = () => api<ShopButton[]>("/admin/shop/buttons");
export const updateButton = (id: number, body: Record<string, unknown>) =>
  api<ShopButton>(`/admin/shop/buttons/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const resetShop = () => api<{ reset: boolean }>("/admin/shop/reset", { method: "POST" });

// --- Settings ---------------------------------------------------------------

export interface CryptoSettings {
  rate_mode: string;
  margin_percent: number;
  manual_rate_usdt: number;
  manual_rate_ton: number;
}
export const getCryptoSettings = () => api<CryptoSettings>("/admin/settings/crypto");
export const setRateMode = (mode: string) =>
  api("/admin/settings/crypto/rate-mode", { method: "PUT", body: JSON.stringify({ mode }) });
export const setMargin = (percent: number) =>
  api("/admin/settings/crypto/margin", { method: "PUT", body: JSON.stringify({ percent }) });
export const setManualRate = (coin: string, toman_per_unit: number) =>
  api("/admin/settings/crypto/manual-rate", {
    method: "PUT",
    body: JSON.stringify({ coin, toman_per_unit }),
  });

export interface RialSettings {
  min_amount_toman: number;
  phone_required: boolean;
  source_card_required: boolean;
  support_handle: string;
  payment_mode: "receipt_bot" | "direct_support";
  destination_card_number: string;
  destination_card_holder: string;
  receipt_valid_minutes: number;
  receipt_bot_username: string;
  receipt_admin_ids: number[];
}
export const getRialSettings = () => api<RialSettings>("/admin/settings/rial");
export const setRialSettings = (body: Partial<RialSettings>) =>
  api<RialSettings>("/admin/settings/rial", { method: "PUT", body: JSON.stringify(body) });

export interface HooshPaySettings {
  enabled: boolean;
  min_amount_toman: number;
  fee_mode: "seller" | "buyer" | "split";
  api_base_url: string;
  callback_base_url: string;
  title: string;
  subtitle: string;
  amount_label: string;
  create_button: string;
  pay_button: string;
  preset_amounts: number[];
  api_key_configured: boolean;
  api_secret_configured: boolean;
}
export const getHooshPaySettings = () => api<HooshPaySettings>("/admin/settings/hooshpay");
export const setHooshPaySettings = (
  body: Partial<HooshPaySettings> & { api_key?: string; api_secret?: string }
) => api<HooshPaySettings>("/admin/settings/hooshpay", { method: "PUT", body: JSON.stringify(body) });

export interface TrialSettings {
  enabled: boolean;
  volume_mb: number;
  duration_hours: number;
  panel_key: string;
  time_mode: "date" | "on_hold" | "unlimited";
  panels: Array<{
    key: string;
    title: string;
    panel_type: string;
    is_enabled: boolean;
  }>;
}
export const getTrialSettings = () => api<TrialSettings>("/admin/settings/trial");
export const setTrialSettings = (body: Partial<TrialSettings>) =>
  api<TrialSettings>("/admin/settings/trial", { method: "PUT", body: JSON.stringify(body) });

export interface BrandedLinksSettings {
  enabled: boolean;
  subscription_profile_title: string;
  subscription_device_limit: number;
}
export const getBrandedLinks = () => api<BrandedLinksSettings>("/admin/settings/branded-links");
export const setBrandedLinks = (enabled: boolean) =>
  api<BrandedLinksSettings>("/admin/settings/branded-links", {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
export const setSubscriptionProfileTitle = (title: string) =>
  api<{ subscription_profile_title: string }>("/admin/settings/subscription-profile-title", {
    method: "PUT",
    body: JSON.stringify({ title }),
  });
export const setSubscriptionDeviceLimit = (limit: number) =>
  api<{ subscription_device_limit: number }>("/admin/settings/subscription-device-limit", {
    method: "PUT",
    body: JSON.stringify({ limit }),
  });

export interface Channel {
  id: number;
  chat_id: string;
  title: string;
  join_url: string;
  is_active: boolean;
}
export const listChannels = () => api<Channel[]>("/admin/required-channels");
export const upsertChannel = (body: { chat_id: string; title: string; join_url: string }) =>
  api<Channel>("/admin/required-channels", { method: "POST", body: JSON.stringify(body) });
export const toggleChannel = (id: number) =>
  api<Channel>(`/admin/required-channels/${id}/toggle`, { method: "POST" });
export const deleteChannel = (id: number) =>
  api<{ deleted: boolean }>(`/admin/required-channels/${id}`, { method: "DELETE" });

// --- Broadcast & admins -----------------------------------------------------

export const sendBroadcast = (text: string, parse_mode: string | null) =>
  api<{ queued: number }>("/admin/broadcast", {
    method: "POST",
    body: JSON.stringify({ text, parse_mode }),
  });

export interface AdminAccount {
  telegram_id: number;
  permissions: string;
  is_owner: boolean;
  is_active: boolean;
}
export const listAdmins = () => api<AdminAccount[]>("/admin/admins");
export const addAdmin = (telegram_id: number, permissions: string) =>
  api<AdminAccount>("/admin/admins", {
    method: "POST",
    body: JSON.stringify({ telegram_id, permissions }),
  });
export const setAdminPermissions = (telegram_id: number, permissions: string) =>
  api<AdminAccount>(`/admin/admins/${telegram_id}/permissions`, {
    method: "PUT",
    body: JSON.stringify({ permissions }),
  });
export const removeAdmin = (telegram_id: number) =>
  api<{ removed: boolean }>(`/admin/admins/${telegram_id}`, { method: "DELETE" });

// --- Users (pagination + detail) --------------------------------------------

export interface UserPurchaseSummary {
  total_count: number;
  total_gb: number;
  total_spent: number;
  purchases: {
    id: number;
    config_id: number;
    volume_gb: number;
    category_key: string;
    price: number;
    service_name: string | null;
    kind: string;
    provision_source: string;
    coupon_code: string | null;
    purchased_at: string;
    renewed_at: string | null;
    panel_key: string | null;
    panel_username: string | null;
    panel_deleted_at: string | null;
    sub_link: string | null;
    public_sub_token: string | null;
    public_url: string | null;
  }[];
}
export const countUsers = (q?: string) =>
  api<{ total: number }>(`/admin/users/count${q ? `?q=${encodeURIComponent(q)}` : ""}`);
export const getUserPurchases = (telegram_id: number) =>
  api<UserPurchaseSummary>(`/admin/users/${telegram_id}/purchases`);
export const deleteUserPurchase = (telegram_id: number, purchase_id: number) =>
  api<{ deleted: boolean }>(`/admin/users/${telegram_id}/purchases/${purchase_id}`, { method: "DELETE" });
export const deleteUserPanelConfig = (telegram_id: number, config_id: number) =>
  api<{ deleted: boolean; already_deleted?: boolean }>(`/admin/users/${telegram_id}/configs/${config_id}/panel`, {
    method: "DELETE",
  });
export const renewUserPurchase = (telegram_id: number, purchase_id: number) =>
  api<{ renewed: boolean; purchase_id: number }>(`/admin/users/${telegram_id}/purchases/${purchase_id}/renew`, {
    method: "POST",
  });
export const resetUserSubscriptionDevices = (telegram_id: number, config_id: number) =>
  api<{ reset: boolean }>(`/admin/users/${telegram_id}/configs/${config_id}/devices/reset`, {
    method: "POST",
  });
export const revokeUserSubscriptionLink = (telegram_id: number, config_id: number) =>
  api<{ revoked: boolean; old_token: string; token: string; public_url: string }>(
    `/admin/users/${telegram_id}/configs/${config_id}/revoke-subscription`,
    { method: "POST" },
  );
