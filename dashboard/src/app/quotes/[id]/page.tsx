"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { Quote, QUOTE_STATUS_COLORS } from "@/lib/types";
import { clsx } from "clsx";

export default function QuoteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const q = await api.quotes.get(id);
        setQuote(q);
      } catch (err) {
        console.error("Failed to load quote:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleStatusUpdate(status: string) {
    setActionLoading(true);
    try {
      const updated = await api.quotes.updateStatus(id, status);
      setQuote(updated);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleConvertToOrder() {
    setActionLoading(true);
    try {
      const order = await api.quotes.convertToOrder(id, {});
      router.push(`/orders/${order.id}`);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return <div><Header title="Quote Details" /><p className="text-mid-warm">Loading...</p></div>;
  }
  if (!quote) {
    return <div><Header title="Quote Details" /><p className="text-mid-warm">Quote not found</p></div>;
  }

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

  return (
    <div>
      <Header title={quote.quote_number} />

      {/* Quote Header */}
      <div className="bg-white rounded-lg border border-rich-creme p-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className={clsx("inline-flex items-center px-3 py-1 rounded-full text-sm font-bold", QUOTE_STATUS_COLORS[quote.status])}>
              {quote.status}
            </span>
            <span className="text-sm text-mid-warm">
              Valid: {new Date(quote.valid_from).toLocaleDateString("en-IN")} - {new Date(quote.valid_until).toLocaleDateString("en-IN")}
            </span>
          </div>
          <div className="flex gap-2">
            {quote.status === "draft" && (
              <Button size="sm" disabled={actionLoading} onClick={() => handleStatusUpdate("sent")}>
                Mark as Sent
              </Button>
            )}
            {quote.status === "sent" && (
              <Button size="sm" variant="secondary" disabled={actionLoading} onClick={() => handleStatusUpdate("viewed")}>
                Mark as Viewed
              </Button>
            )}
            {["sent", "viewed"].includes(quote.status) && (
              <>
                <Button size="sm" disabled={actionLoading} onClick={() => handleStatusUpdate("accepted")}>
                  Accept
                </Button>
                <Button size="sm" variant="danger" disabled={actionLoading} onClick={() => handleStatusUpdate("rejected")}>
                  Reject
                </Button>
              </>
            )}
            {quote.status === "accepted" && !quote.converted_to_order_id && (
              <Button size="sm" disabled={actionLoading} onClick={handleConvertToOrder}>
                Convert to Order
              </Button>
            )}
          </div>
        </div>
        {quote.sent_at && <p className="text-xs text-mid-warm mt-2">Sent: {new Date(quote.sent_at).toLocaleString("en-IN")}</p>}
        {quote.viewed_at && <p className="text-xs text-mid-warm">Viewed: {new Date(quote.viewed_at).toLocaleString("en-IN")}</p>}
        {quote.accepted_at && <p className="text-xs text-mid-warm">Accepted: {new Date(quote.accepted_at).toLocaleString("en-IN")}</p>}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Line Items */}
        <div className="col-span-2">
          <div className="bg-white rounded-lg border border-rich-creme overflow-hidden">
            <div className="px-4 py-3 bg-creme/30 border-b border-rich-creme">
              <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase">Line Items</h4>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rich-creme">
                  <th className="text-left px-4 py-2 text-xs text-mid-warm">Product</th>
                  <th className="text-right px-4 py-2 text-xs text-mid-warm">Qty</th>
                  <th className="text-right px-4 py-2 text-xs text-mid-warm">Unit Price</th>
                  <th className="text-right px-4 py-2 text-xs text-mid-warm">Total</th>
                </tr>
              </thead>
              <tbody>
                {(quote.line_items || []).map((item) => (
                  <tr key={item.id} className="border-b border-rich-creme/50">
                    <td className="px-4 py-3">
                      <p className="font-bold text-warm-charcoal">{item.product_name}</p>
                      {item.color && <p className="text-xs text-mid-warm">Color: {item.color}</p>}
                      {item.gsm && <p className="text-xs text-mid-warm">GSM: {item.gsm}</p>}
                      {item.customization_type && <p className="text-xs text-mid-warm">{item.customization_type}</p>}
                    </td>
                    <td className="px-4 py-3 text-right">{item.quantity}</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(item.unit_price)}</td>
                    <td className="px-4 py-3 text-right font-bold">{formatCurrency(item.total_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-3 bg-creme/20 text-sm">
              <div className="flex justify-between"><span className="text-mid-warm">Subtotal</span><span>{formatCurrency(quote.subtotal)}</span></div>
              {quote.discount_amount > 0 && (
                <div className="flex justify-between"><span className="text-mid-warm">Discount ({quote.discount_percent}%)</span><span>-{formatCurrency(quote.discount_amount)}</span></div>
              )}
              <div className="flex justify-between"><span className="text-mid-warm">GST ({quote.gst_rate}%)</span><span>{formatCurrency(quote.gst_amount)}</span></div>
              <div className="flex justify-between font-bold text-crimson-dark border-t border-rich-creme pt-2 mt-2">
                <span>Total</span><span>{formatCurrency(quote.total_amount)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-rich-creme p-4">
            <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Details</h4>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-mid-warm">Currency</dt>
                <dd className="font-bold">{quote.currency}</dd>
              </div>
              {quote.payment_terms && (
                <div className="flex justify-between">
                  <dt className="text-mid-warm">Payment Terms</dt>
                  <dd className="font-bold text-right">{quote.payment_terms}</dd>
                </div>
              )}
              {quote.delivery_terms && (
                <div className="flex justify-between">
                  <dt className="text-mid-warm">Delivery Terms</dt>
                  <dd className="font-bold text-right">{quote.delivery_terms}</dd>
                </div>
              )}
            </dl>
          </div>

          {quote.notes && (
            <div className="bg-white rounded-lg border border-rich-creme p-4">
              <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Notes</h4>
              <p className="text-sm text-warm-charcoal whitespace-pre-line">{quote.notes}</p>
            </div>
          )}

          {quote.terms_and_conditions && (
            <div className="bg-white rounded-lg border border-rich-creme p-4">
              <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Terms & Conditions</h4>
              <p className="text-xs text-warm-charcoal whitespace-pre-line">{quote.terms_and_conditions}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
