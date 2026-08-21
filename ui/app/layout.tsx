import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const siteUrl = process.env.SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "WEALTH OS — Observe & Validate",
  description: "A deterministic research interface for observing and auditing the WEALTH OS trading loop.",
  openGraph: {
    title: "WEALTH OS",
    description: "Observe & Validate",
    images: [{ url: "/og.png", width: 1734, height: 907, alt: "WEALTH OS — Observe & Validate" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "WEALTH OS",
    description: "Observe & Validate",
    images: ["/og.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
