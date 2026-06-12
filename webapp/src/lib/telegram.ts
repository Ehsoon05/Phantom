"use client";

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { start_param?: string; user?: { id: number; first_name: string } };
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  ready: () => void;
  expand: () => void;
  onEvent: (event: string, cb: () => void) => void;
  HapticFeedback?: { notificationOccurred: (type: "success" | "error" | "warning") => void };
  openTelegramLink: (url: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getWebApp(): TelegramWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

/** Map Telegram themeParams onto the shadcn CSS variables so the app
 *  matches the user's Telegram theme (light and dark) automatically. */
export function applyTelegramTheme(tg: TelegramWebApp) {
  const root = document.documentElement;
  const p = tg.themeParams;
  const map: Record<string, string | undefined> = {
    "--background": p.bg_color,
    "--foreground": p.text_color,
    "--card": p.secondary_bg_color,
    "--card-foreground": p.text_color,
    "--primary": p.button_color,
    "--primary-foreground": p.button_text_color,
    "--muted-foreground": p.hint_color,
    "--accent": p.secondary_bg_color,
    "--border": p.section_separator_color ?? p.hint_color,
  };
  for (const [cssVar, value] of Object.entries(map)) {
    if (value) root.style.setProperty(cssVar, value);
  }
  root.classList.toggle("dark", tg.colorScheme === "dark");
}
