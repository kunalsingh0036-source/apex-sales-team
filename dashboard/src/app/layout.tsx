import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";

export const metadata: Metadata = {
  title: "Apex Human - Outreach Agent",
  description: "AI-powered sales outreach system for The Apex Human Company",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Sidebar />
        <main className="ml-60 min-h-screen p-8">{children}</main>
      </body>
    </html>
  );
}
