"use client";

import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import { ToastProvider } from "@/components/ui/Toast";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <ToastProvider>
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="ml-0 md:ml-60 min-h-screen px-4 md:px-10 py-4 md:py-8">
        <div className="md:hidden flex items-center gap-3 mb-4">
          <button onClick={() => setSidebarOpen(true)} className="text-crimson-dark text-2xl">&#9776;</button>
          <h1 className="font-display text-lg font-bold text-crimson-dark">APEX HUMAN</h1>
        </div>
        {children}
      </main>
    </ToastProvider>
  );
}
