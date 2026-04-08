"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

const outreachItems = [
  { href: "/", label: "Dashboard", icon: "◉" },
  { href: "/leads", label: "Leads", icon: "◎" },
  { href: "/campaigns", label: "Campaigns", icon: "▶" },
  { href: "/messages", label: "Messages", icon: "✉" },
  { href: "/analytics", label: "Analytics", icon: "◈" },
  { href: "/autopilot", label: "Autopilot", icon: "⚡" },
];

const crmItems = [
  { href: "/clients", label: "Clients", icon: "◇" },
  { href: "/orders", label: "Orders", icon: "▦" },
  { href: "/products", label: "Products", icon: "▣" },
  { href: "/quotes", label: "Quotes", icon: "▤" },
];

const bottomItems = [
  { href: "/settings", label: "Settings", icon: "⚙" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-crimson-dark text-creme flex flex-col">
      <div className="p-6 border-b border-crimson">
        <h1 className="font-display text-lg font-bold tracking-wide">
          THE APEX HUMAN
        </h1>
        <p className="font-label text-xs tracking-[0.2em] mt-1 text-rich-creme opacity-80 uppercase">
          Sales Agent
        </p>
      </div>

      <nav className="flex-1 py-4 overflow-y-auto">
        {outreachItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-6 py-3 text-sm transition-colors",
                isActive
                  ? "bg-crimson text-creme font-bold"
                  : "text-rich-creme hover:bg-crimson/50 hover:text-creme"
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}

        <div className="mx-6 my-3 border-t border-crimson/40" />
        <p className="px-6 py-1 font-label text-[10px] tracking-[0.2em] text-mid-warm uppercase">
          CRM
        </p>

        {crmItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-6 py-3 text-sm transition-colors",
                isActive
                  ? "bg-crimson text-creme font-bold"
                  : "text-rich-creme hover:bg-crimson/50 hover:text-creme"
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}

        <div className="mx-6 my-3 border-t border-crimson/40" />

        {bottomItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-6 py-3 text-sm transition-colors",
                isActive
                  ? "bg-crimson text-creme font-bold"
                  : "text-rich-creme hover:bg-crimson/50 hover:text-creme"
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-crimson">
        <p className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">
          Buy from the source.
          <br />
          Wear the standard.
        </p>
      </div>
    </aside>
  );
}
