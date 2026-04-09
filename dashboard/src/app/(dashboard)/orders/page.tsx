"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";
import {
  Order, PaginatedResponse, OrderStage,
  ORDER_STAGE_LABELS, ORDER_STAGE_COLORS,
} from "@/lib/types";
import { clsx } from "clsx";

const ALL_STAGES: OrderStage[] = ["brief", "design", "tech_spec", "sampling", "production", "qc", "delivery"];

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [viewMode, setViewMode] = useState<"kanban" | "table">("kanban");
  const [pipeline, setPipeline] = useState<any>(null);
  const [showModal, setShowModal] = useState(false);
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [orderForm, setOrderForm] = useState({ client_id: "", priority: "normal", notes: "" });

  async function fetchOrders() {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: 100 };
      if (stageFilter) params.stage = stageFilter;
      if (priorityFilter) params.priority = priorityFilter;
      const [data, pipe] = await Promise.all([
        api.orders.list(params),
        api.orders.pipeline(),
      ]);
      setOrders(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setPipeline(pipe);
    } catch (err) {
      console.error("Failed to fetch orders:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchOrders();
  }, [page, stageFilter, priorityFilter]);

  async function handleCreateOrder(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.orders.create({
        client_id: orderForm.client_id,
        priority: orderForm.priority,
        notes: orderForm.notes,
      });
      setShowModal(false);
      setOrderForm({ client_id: "", priority: "normal", notes: "" });
      fetchOrders();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteOrder(order: Order) {
    if (!confirm(`Delete order "${order.order_number}"?`)) return;
    try {
      await api.orders.delete(order.id);
      toast("Order deleted", "success");
      fetchOrders();
    } catch (err: any) {
      toast(err.message || "Failed to delete order", "error");
    }
  }

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

  const ordersByStage = ALL_STAGES.reduce((acc, stage) => {
    acc[stage] = orders.filter((o) => o.stage === stage);
    return acc;
  }, {} as Record<OrderStage, Order[]>);

  return (
    <div>
      <Header title="Orders" />

      <div className="flex justify-end mb-6">
        <Button size="sm" onClick={() => setShowModal(true)}>+ New Order</Button>
      </div>

      {/* New Order Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold mb-4">New Order</h2>
            <form onSubmit={handleCreateOrder} className="space-y-3">
              <input
                type="text"
                placeholder="Client ID"
                value={orderForm.client_id}
                onChange={(e) => setOrderForm({ ...orderForm, client_id: e.target.value })}
                required
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <select
                value={orderForm.priority}
                onChange={(e) => setOrderForm({ ...orderForm, priority: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
              <textarea
                placeholder="Notes"
                value={orderForm.notes}
                onChange={(e) => setOrderForm({ ...orderForm, notes: e.target.value })}
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

      {/* Pipeline Summary */}
      {pipeline && (
        <div className="grid grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl border border-rich-creme p-5">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Orders</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{pipeline.total_orders}</p>
          </div>
          <div className="bg-white rounded-xl border border-rich-creme p-5">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Pipeline Value</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{formatCurrency(pipeline.total_pipeline_value)}</p>
          </div>
          <div className="bg-white rounded-xl border border-rich-creme p-5 col-span-2">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-2">By Stage</p>
            <div className="flex gap-2 flex-wrap">
              {(pipeline.stages || []).map((s: any) => (
                <span key={s.stage} className={clsx("inline-flex items-center px-2 py-1 rounded text-xs font-bold", ORDER_STAGE_COLORS[s.stage as OrderStage] || "bg-gray-100")}>
                  {ORDER_STAGE_LABELS[s.stage as OrderStage] || s.stage}: {s.count}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex gap-2">
          <select
            value={stageFilter}
            onChange={(e) => { setStageFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded border border-rich-creme bg-white text-sm"
          >
            <option value="">All Stages</option>
            {ALL_STAGES.map((s) => (
              <option key={s} value={s}>{ORDER_STAGE_LABELS[s]}</option>
            ))}
          </select>
          <select
            value={priorityFilter}
            onChange={(e) => { setPriorityFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded border border-rich-creme bg-white text-sm"
          >
            <option value="">All Priorities</option>
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>
        <div className="flex gap-1 bg-rich-creme rounded p-0.5">
          <button
            onClick={() => setViewMode("kanban")}
            className={clsx("px-3 py-1 text-xs font-bold rounded transition-colors", viewMode === "kanban" ? "bg-crimson text-creme" : "text-warm-charcoal")}
          >
            Kanban
          </button>
          <button
            onClick={() => setViewMode("table")}
            className={clsx("px-3 py-1 text-xs font-bold rounded transition-colors", viewMode === "table" ? "bg-crimson text-creme" : "text-warm-charcoal")}
          >
            Table
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-mid-warm text-center py-8">Loading...</p>
      ) : viewMode === "kanban" ? (
        /* Kanban View */
        <div className="flex gap-3 overflow-x-auto pb-4">
          {ALL_STAGES.map((stage) => (
            <div key={stage} className="min-w-[240px] flex-1">
              <div className={clsx("rounded-t-xl px-3 py-2 text-xs font-bold", ORDER_STAGE_COLORS[stage])}>
                {ORDER_STAGE_LABELS[stage]} ({ordersByStage[stage].length})
              </div>
              <div className="bg-gray-50 rounded-b-xl p-2 space-y-2 min-h-[200px]">
                {ordersByStage[stage].map((order) => (
                  <div
                    key={order.id}
                    className="bg-white rounded border border-rich-creme p-4 hover:shadow transition-shadow"
                  >
                    <Link href={`/orders/${order.id}`} className="block">
                      <p className="font-bold text-xs text-crimson-dark">{order.order_number}</p>
                      <p className="text-xs text-mid-warm mt-1">{formatCurrency(order.total_amount)}</p>
                      {order.priority !== "normal" && (
                        <Badge variant={order.priority === "urgent" ? "danger" : order.priority === "high" ? "warning" : "default"} className="mt-1">
                          {order.priority}
                        </Badge>
                      )}
                    </Link>
                    <div className="mt-2 pt-2 border-t border-rich-creme flex justify-end">
                      <button
                        onClick={() => handleDeleteOrder(order)}
                        className="px-2 py-0.5 text-[10px] font-bold text-red-600 hover:bg-red-50 rounded transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="bg-white rounded-xl border border-rich-creme overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rich-creme bg-creme/30">
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Order #</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Stage</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Total</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Priority</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Created</th>
                <th className="text-right px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-mid-warm">No orders found</td></tr>
              ) : orders.map((order) => (
                <tr key={order.id} className="border-b border-rich-creme/50 hover:bg-creme/20 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/orders/${order.id}`} className="font-bold text-crimson-dark hover:text-crimson">
                      {order.order_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={clsx("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold", ORDER_STAGE_COLORS[order.stage])}>
                      {ORDER_STAGE_LABELS[order.stage]}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-bold text-warm-charcoal">{formatCurrency(order.total_amount)}</td>
                  <td className="px-4 py-3">
                    <Badge variant={order.priority === "urgent" ? "danger" : order.priority === "high" ? "warning" : "default"}>
                      {order.priority}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-mid-warm">{new Date(order.created_at).toLocaleDateString("en-IN")}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDeleteOrder(order)}
                      className="px-2.5 py-1 text-xs font-bold text-red-600 hover:bg-red-50 rounded transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
