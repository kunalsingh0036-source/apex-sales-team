"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
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

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

  const ordersByStage = ALL_STAGES.reduce((acc, stage) => {
    acc[stage] = orders.filter((o) => o.stage === stage);
    return acc;
  }, {} as Record<OrderStage, Order[]>);

  return (
    <div>
      <Header title="Orders" />

      {/* Pipeline Summary */}
      {pipeline && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg border border-rich-creme p-4">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Orders</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{pipeline.total_orders}</p>
          </div>
          <div className="bg-white rounded-lg border border-rich-creme p-4">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Pipeline Value</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{formatCurrency(pipeline.total_pipeline_value)}</p>
          </div>
          <div className="bg-white rounded-lg border border-rich-creme p-4 col-span-2">
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
            <div key={stage} className="min-w-[220px] flex-1">
              <div className={clsx("rounded-t-lg px-3 py-2 text-xs font-bold", ORDER_STAGE_COLORS[stage])}>
                {ORDER_STAGE_LABELS[stage]} ({ordersByStage[stage].length})
              </div>
              <div className="bg-gray-50 rounded-b-lg p-2 space-y-2 min-h-[200px]">
                {ordersByStage[stage].map((order) => (
                  <Link
                    key={order.id}
                    href={`/orders/${order.id}`}
                    className="block bg-white rounded border border-rich-creme p-3 hover:shadow transition-shadow"
                  >
                    <p className="font-bold text-xs text-crimson-dark">{order.order_number}</p>
                    <p className="text-xs text-mid-warm mt-1">{formatCurrency(order.total_amount)}</p>
                    {order.priority !== "normal" && (
                      <Badge variant={order.priority === "urgent" ? "danger" : order.priority === "high" ? "warning" : "default"} className="mt-1">
                        {order.priority}
                      </Badge>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="bg-white rounded-lg border border-rich-creme overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rich-creme bg-creme/30">
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Order #</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Stage</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Total</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Priority</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Created</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-mid-warm">No orders found</td></tr>
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
