"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { Order, OrderStageLog, OrderStage, ORDER_STAGE_LABELS, ORDER_STAGE_COLORS } from "@/lib/types";
import { clsx } from "clsx";

const ALL_STAGES: OrderStage[] = ["brief", "design", "tech_spec", "sampling", "production", "qc", "delivery"];

const VALID_TRANSITIONS: Record<string, string[]> = {
  brief: ["design"],
  design: ["tech_spec", "brief"],
  tech_spec: ["sampling", "design"],
  sampling: ["production", "tech_spec"],
  production: ["qc"],
  qc: ["delivery", "production"],
  delivery: [],
};

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [stageHistory, setStageHistory] = useState<OrderStageLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [stageNotes, setStageNotes] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [o, history] = await Promise.all([
          api.orders.get(id),
          api.orders.stageHistory(id),
        ]);
        setOrder(o);
        setStageHistory(history);
      } catch (err) {
        console.error("Failed to load order:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleAdvanceStage(toStage: string) {
    setAdvancing(true);
    try {
      const updated = await api.orders.advanceStage(id, { to_stage: toStage, notes: stageNotes });
      setOrder(updated);
      setStageNotes("");
      const history = await api.orders.stageHistory(id);
      setStageHistory(history);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setAdvancing(false);
    }
  }

  if (loading) {
    return <div><Header title="Order Details" /><p className="text-mid-warm">Loading...</p></div>;
  }
  if (!order) {
    return <div><Header title="Order Details" /><p className="text-mid-warm">Order not found</p></div>;
  }

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

  const nextStages = VALID_TRANSITIONS[order.stage] || [];
  const currentIdx = ALL_STAGES.indexOf(order.stage);

  return (
    <div>
      <Header title={order.order_number} />

      {/* Stage Progress Bar */}
      <div className="bg-white rounded-xl border border-rich-creme p-8 mb-6">
        <div className="flex items-center justify-between">
          {ALL_STAGES.map((stage, idx) => {
            const isPast = idx < currentIdx;
            const isCurrent = idx === currentIdx;
            return (
              <div key={stage} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  <div
                    className={clsx(
                      "w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold",
                      isCurrent ? "bg-crimson text-creme" :
                      isPast ? "bg-green-500 text-white" :
                      "bg-rich-creme text-mid-warm"
                    )}
                  >
                    {isPast ? "✓" : idx + 1}
                  </div>
                  <span className={clsx("text-xs mt-1", isCurrent ? "font-bold text-crimson" : "text-mid-warm")}>
                    {ORDER_STAGE_LABELS[stage]}
                  </span>
                </div>
                {idx < ALL_STAGES.length - 1 && (
                  <div className={clsx("h-0.5 flex-1 mx-1", isPast ? "bg-green-500" : "bg-rich-creme")} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Stage Advancement */}
      {nextStages.length > 0 && (
        <div className="bg-white rounded-xl border border-rich-creme p-4 mb-6">
          <div className="flex items-center gap-4">
            <input
              type="text"
              value={stageNotes}
              onChange={(e) => setStageNotes(e.target.value)}
              placeholder="Stage transition notes..."
              className="flex-1 px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson"
            />
            {nextStages.map((stage) => (
              <Button
                key={stage}
                size="sm"
                variant={stage === nextStages[0] ? "primary" : "outline"}
                disabled={advancing}
                onClick={() => handleAdvanceStage(stage)}
              >
                {ORDER_STAGE_LABELS[stage as OrderStage]}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Order Info */}
        <div className="col-span-2 space-y-6">
          {/* Line Items */}
          <div className="bg-white rounded-xl border border-rich-creme overflow-hidden">
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
                {(order.line_items || []).map((item) => (
                  <tr key={item.id} className="border-b border-rich-creme/50">
                    <td className="px-4 py-3">
                      <p className="font-bold text-warm-charcoal">{item.product_name}</p>
                      {item.color && <p className="text-xs text-mid-warm">Color: {item.color}</p>}
                      {item.gsm && <p className="text-xs text-mid-warm">GSM: {item.gsm}</p>}
                      {item.customization_type && <p className="text-xs text-mid-warm">Customization: {item.customization_type}</p>}
                    </td>
                    <td className="px-4 py-3 text-right">{item.quantity}</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(item.unit_price)}</td>
                    <td className="px-4 py-3 text-right font-bold">{formatCurrency(item.total_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-3 bg-creme/20 text-sm">
              <div className="flex justify-between"><span className="text-mid-warm">Subtotal</span><span>{formatCurrency(order.subtotal)}</span></div>
              {order.discount_amount > 0 && (
                <div className="flex justify-between"><span className="text-mid-warm">Discount ({order.discount_percent}%)</span><span>-{formatCurrency(order.discount_amount)}</span></div>
              )}
              <div className="flex justify-between"><span className="text-mid-warm">GST ({order.gst_rate}%)</span><span>{formatCurrency(order.gst_amount)}</span></div>
              <div className="flex justify-between font-bold text-crimson-dark border-t border-rich-creme pt-2 mt-2">
                <span>Total</span><span>{formatCurrency(order.total_amount)}</span>
              </div>
            </div>
          </div>

          {/* Stage History */}
          <div className="bg-white rounded-xl border border-rich-creme p-4">
            <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-4">Stage History</h4>
            <div className="space-y-3">
              {stageHistory.map((log) => (
                <div key={log.id} className="flex items-start gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-crimson mt-1.5 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-warm-charcoal">
                      {log.from_stage ? (
                        <><span className="font-bold">{ORDER_STAGE_LABELS[log.from_stage as OrderStage] || log.from_stage}</span> → </>
                      ) : null}
                      <span className="font-bold">{ORDER_STAGE_LABELS[log.to_stage as OrderStage] || log.to_stage}</span>
                    </p>
                    {log.notes && <p className="text-mid-warm text-xs mt-0.5">{log.notes}</p>}
                  </div>
                  <span className="text-xs text-mid-warm flex-shrink-0">
                    {new Date(log.created_at).toLocaleDateString("en-IN")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-rich-creme p-4">
            <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Order Info</h4>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-mid-warm">Priority</dt>
                <dd><Badge variant={order.priority === "urgent" ? "danger" : order.priority === "high" ? "warning" : "default"}>{order.priority}</Badge></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-mid-warm">Currency</dt>
                <dd className="font-bold">{order.currency}</dd>
              </div>
              {order.expected_delivery_date && (
                <div className="flex justify-between">
                  <dt className="text-mid-warm">Expected Delivery</dt>
                  <dd className="font-bold">{new Date(order.expected_delivery_date).toLocaleDateString("en-IN")}</dd>
                </div>
              )}
              {order.actual_delivery_date && (
                <div className="flex justify-between">
                  <dt className="text-mid-warm">Actual Delivery</dt>
                  <dd className="font-bold">{new Date(order.actual_delivery_date).toLocaleDateString("en-IN")}</dd>
                </div>
              )}
            </dl>
          </div>

          {order.notes && (
            <div className="bg-white rounded-xl border border-rich-creme p-4">
              <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Notes</h4>
              <p className="text-sm text-warm-charcoal whitespace-pre-line">{order.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
