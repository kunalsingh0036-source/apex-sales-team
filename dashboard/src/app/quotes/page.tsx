"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { Quote, PaginatedResponse, QUOTE_STATUS_COLORS } from "@/lib/types";
import { clsx } from "clsx";

export default function QuotesPage() {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  async function fetchQuotes() {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: 50 };
      if (statusFilter) params.status = statusFilter;
      const data: PaginatedResponse<Quote> = await api.quotes.list(params);
      setQuotes(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      console.error("Failed to fetch quotes:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchQuotes();
  }, [page, statusFilter]);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

  return (
    <div>
      <Header title="Quotes" />

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg border border-rich-creme p-4">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Quotes</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{total}</p>
        </div>
        <div className="bg-white rounded-lg border border-rich-creme p-4">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Draft</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">
            {quotes.filter((q) => q.status === "draft").length}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-rich-creme p-4">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Pending</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">
            {quotes.filter((q) => ["sent", "viewed"].includes(q.status)).length}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-rich-creme p-4">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Accepted</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">
            {quotes.filter((q) => q.status === "accepted").length}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded border border-rich-creme bg-white text-sm"
        >
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="viewed">Viewed</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="expired">Expired</option>
          <option value="converted">Converted</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-rich-creme overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rich-creme bg-creme/30">
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Quote #</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Status</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Total</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Valid Until</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-mid-warm">Loading...</td></tr>
            ) : quotes.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-mid-warm">No quotes found</td></tr>
            ) : (
              quotes.map((quote) => (
                <tr key={quote.id} className="border-b border-rich-creme/50 hover:bg-creme/20 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/quotes/${quote.id}`} className="font-bold text-crimson-dark hover:text-crimson">
                      {quote.quote_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={clsx("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold", QUOTE_STATUS_COLORS[quote.status] || "bg-gray-100")}>
                      {quote.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-bold text-warm-charcoal">{formatCurrency(quote.total_amount)}</td>
                  <td className="px-4 py-3 text-mid-warm">{new Date(quote.valid_until).toLocaleDateString("en-IN")}</td>
                  <td className="px-4 py-3 text-mid-warm">{new Date(quote.created_at).toLocaleDateString("en-IN")}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-mid-warm">
            Showing {(page - 1) * 50 + 1}-{Math.min(page * 50, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  );
}
