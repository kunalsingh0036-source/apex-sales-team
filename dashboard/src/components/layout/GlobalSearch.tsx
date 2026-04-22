"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";

type Hit = {
  id: string;
  title: string;
  subtitle: string;
  url: string;
  lead_code?: string;
};

type Results = Record<string, Hit[]>;

const CATEGORY_LABELS: Record<string, string> = {
  leads: "Leads",
  companies: "Companies",
  messages: "Messages",
  clients: "Clients",
  orders: "Orders",
  quotes: "Quotes",
  products: "Products",
  campaigns: "Campaigns",
  sequences: "Sequences",
};

export default function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Results | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Cmd+K / Ctrl+K to focus
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
      if (e.key === "Escape") {
        setOpen(false);
        inputRef.current?.blur();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Click outside to close
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  // Debounced search
  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setResults(null);
      return;
    }
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const data = await api.search.global(query.trim());
        setResults(data.results);
        setOpen(true);
        setActiveIdx(0);
      } catch (err) {
        console.error("search error", err);
        setResults(null);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Flatten for keyboard navigation
  const flatHits: { category: string; hit: Hit }[] = [];
  if (results) {
    for (const [category, hits] of Object.entries(results)) {
      for (const hit of hits) flatHits.push({ category, hit });
    }
  }

  function navigate(hit: Hit) {
    setOpen(false);
    setQuery("");
    setResults(null);
    router.push(hit.url);
  }

  function onInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || flatHits.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => (i + 1) % flatHits.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => (i - 1 + flatHits.length) % flatHits.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      navigate(flatHits[activeIdx].hit);
    }
  }

  const hitIndexOffset: Record<string, number> = {};
  let offset = 0;
  if (results) {
    for (const [category, hits] of Object.entries(results)) {
      hitIndexOffset[category] = offset;
      offset += hits.length;
    }
  }

  return (
    <div ref={containerRef} className="relative w-full md:w-96">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (results) setOpen(true); }}
          onKeyDown={onInputKeyDown}
          placeholder="Search leads, messages, orders… (⌘K)"
          className="w-full px-3 py-2 pl-9 bg-white border border-rich-creme rounded-lg text-sm text-warm-charcoal focus:outline-none focus:border-crimson placeholder:text-mid-warm/70"
        />
        <svg
          className="absolute left-2.5 top-2.5 w-4 h-4 text-mid-warm"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 104.5 4.5a7.5 7.5 0 0012.15 12.15z" />
        </svg>
        {loading && (
          <div className="absolute right-3 top-2.5 text-xs text-mid-warm">…</div>
        )}
      </div>

      {open && results && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-rich-creme rounded-lg shadow-xl max-h-[70vh] overflow-y-auto">
          {flatHits.length === 0 ? (
            <div className="px-4 py-6 text-sm text-mid-warm text-center">
              No matches for &quot;{query}&quot;
            </div>
          ) : (
            Object.entries(results).map(([category, hits]) =>
              hits.length > 0 ? (
                <div key={category} className="border-b border-rich-creme/60 last:border-0">
                  <div className="px-4 py-1.5 font-label text-[10px] tracking-[0.2em] text-mid-warm uppercase bg-creme/50">
                    {CATEGORY_LABELS[category] || category}
                  </div>
                  {hits.map((hit, i) => {
                    const globalIdx = (hitIndexOffset[category] ?? 0) + i;
                    const isActive = globalIdx === activeIdx;
                    return (
                      <button
                        key={hit.id}
                        onClick={() => navigate(hit)}
                        onMouseEnter={() => setActiveIdx(globalIdx)}
                        className={`w-full text-left px-4 py-2 flex items-center gap-3 transition-colors ${
                          isActive ? "bg-creme/70" : "hover:bg-creme/40"
                        }`}
                      >
                        {hit.lead_code && (
                          <span className="font-mono text-xs font-bold text-crimson-dark shrink-0">
                            {hit.lead_code}
                          </span>
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-bold text-warm-charcoal truncate">
                            {hit.title || "—"}
                          </div>
                          {hit.subtitle && (
                            <div className="text-xs text-mid-warm truncate">
                              {hit.subtitle}
                            </div>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : null
            )
          )}
        </div>
      )}
    </div>
  );
}
