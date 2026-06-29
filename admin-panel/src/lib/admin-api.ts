import { api } from "./api";

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
  support_handle: string;
}
export const getRialSettings = () => api<RialSettings>("/admin/settings/rial");
export const setRialSettings = (body: Partial<RialSettings>) =>
  api<RialSettings>("/admin/settings/rial", { method: "PUT", body: JSON.stringify(body) });

export interface TrialSettings {
  enabled: boolean;
  volume_mb: number;
  duration_hours: number;
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
    volume_gb: number;
    category_key: string;
    price: number;
    service_name: string | null;
    coupon_code: string | null;
    purchased_at: string;
  }[];
}
export const countUsers = (q?: string) =>
  api<{ total: number }>(`/admin/users/count${q ? `?q=${encodeURIComponent(q)}` : ""}`);
export const getUserPurchases = (telegram_id: number) =>
  api<UserPurchaseSummary>(`/admin/users/${telegram_id}/purchases`);
