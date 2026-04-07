import type { Metadata } from "next";
import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
