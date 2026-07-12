import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Görsel Atölyesi | Yeni Bakış Haber",
  description: "Haber görsellerini kırpın, boyutlandırın ve WebP olarak hazırlayın.",
  icons: { icon: "/yenibakis-logo-square.png", apple: "/yenibakis-logo-square.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
