"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";
import { Quote, PaginatedResponse, QUOTE_STATUS_COLORS } from "@/lib/types";
import { clsx } from "clsx";

export default function QuotesPage() {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [quoteForm, setQuoteForm] = useState({ client_id: "", total_amount: "", valid_until: "", notes: "" });

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

  async function handleCreateQuote(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.quotes.create({
        client_id: quoteForm.client_id,
        total_amount: Number(quoteForm.total_amount),
        valid_until: quoteForm.valid_until,
        notes: quoteForm.notes,
      });
      setShowModal(false);
      setQuoteForm({ client_id: "", total_amount: "", valid_until: "", notes: "" });
      fetchQuotes();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setSaving(false);
    }
  }

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

  return (
    <div>
      <Header title="Quotes" />

      <div className="flex justify-end mb-6">
        <Button size="sm" onClick={() => setShowModal(true)}>+ New Quote</Button>
      </div>

      {/* New Quote Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold mb-4">New Quote</h2>
            <form onSubmit={handleCreateQuote} className="space-y-3">
              <input
                type="text"
                placeholder="Client ID"
                value={quoteForm.client_id}
                onChange={(e) => setQuoteForm({ ...quoteForm, client_id: e.target.value })}
                required
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <input
                type="number"
                placeholder="Total Amount"
                value={quoteForm.total_amount}
                onChange={(e) => setQuoteForm({ ...quoteForm, total_amount: e.target.value })}
                required
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <input
                type="date"
                placeholder="Valid Until"
                value={quoteForm.valid_until}
                onChange={(e) => setQuoteForm({ ...quoteForm, valid_until: e.target.value })}
                required
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <textarea
                placeholder="Notes"
                value={quoteForm.notes}
                onChange={(e) => setQuoteForm({ ...quoteForm, notes: e.target.value })}
                rows={3}
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <div className="flex gap-2 justify-end mt-4">
                <Button variant="outline" size="sm" type="button" onClick={() => setShowModal(false)}>Cancel</Button>
                <Button size="sm" type="submit" disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-5 mb-8">
        <div className="bg-white rounded-xl border border-rich-creme p-5">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Quotes</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{total}</p>
        </div>
        <div className="bg-white rounded-xl border border-rich-creme p-5">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Draft</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">
            {quotes.filter((q) => q.status === "draft").length}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-rich-creme p-5">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Pending</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">
            {quotes.filter((q) => ["sent", "viewed"].includes(q.status)).length}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-rich-creme p-5">
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
      <div className="bg-white rounded-xl border border-rich-creme overflow-hidden">
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
