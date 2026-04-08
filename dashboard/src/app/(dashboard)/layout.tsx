"use client";

import Sidebar from "@/components/layout/Sidebar";
import { ToastProvider } from "@/components/ui/Toast";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      <Sidebar />
      <main className="ml-60 min-h-screen px-10 py-8">{children}</main>
    </ToastProvider>
  );
}
