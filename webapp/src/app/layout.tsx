import type { Metadata, Viewport } from "next";
import { Vazirmatn } from "next/font/google";
import Script from "next/script";

import { BottomNav } from "@/components/bottom-nav";
import { Providers } from "@/components/providers";

import "./globals.css";

const vazirmatn = Vazirmatn({ subsets: ["arabic"], variable: "--font-vazirmatn" });

export const metadata: Metadata = {
  title: "Phantom Shop",
  description: "فروشگاه فانتوم",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
      </head>
      <body className={`${vazirmatn.variable} font-[family-name:var(--font-vazirmatn)] antialiased`}>
        <Providers>
          <main className="mx-auto min-h-dvh max-w-md px-4 pb-24 pt-4">{children}</main>
          <BottomNav />
        </Providers>
      </body>
    </html>
  );
}
