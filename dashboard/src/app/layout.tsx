import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";

export const metadata: Metadata = {
  title: "Apex Human - Sales Agent",
  description: "AI-powered sales system for The Apex Human Company",
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
        <main className="ml-60 min-h-screen px-10 py-8">{children}</main>
      </body>
    </html>
  );
}
