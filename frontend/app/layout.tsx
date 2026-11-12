import type { Metadata } from "next";
import { Inter, Sora } from "next/font/google";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const sora = Sora({ variable: "--font-sora", subsets: ["latin"], weight: ["600", "700"] });

export const metadata: Metadata = {
  title: "TeamBase | A Django and Next.js SaaS starter",
  description:
    "Multi-tenant SaaS starter: email sign-up, organisations, roles, invitations, plans with seat limits, Stripe billing and an audit log. Django REST backend, Next.js frontend. Open source, by Devomio.",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${sora.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
