"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";

function MetricCard({
  label,
  value,
  subtext,
}: {
  label: string;
  value: string;
  subtext?: string;
}) {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-rich-creme">
      <p className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-2">
        {label}
      </p>
      <p className="font-display text-3xl font-bold text-crimson-dark">
        {value}
      </p>
      {subtext && (
        <p className="text-sm text-mid-warm mt-1">{subtext}</p>
      )}
    </div>
  );
}

const STAGE_CONFIG: { key: string; label: string; color: string }[] = [
  { key: "prospect", label: "Prospect", color: "bg-gray-400" },
  { key: "contacted", label: "Contacted", color: "bg-blue-400" },
  { key: "engaged", label: "Engaged", color: "bg-amber-400" },
  { key: "qualified", label: "Qualified", color: "bg-purple-400" },
  { key: "proposal_sent", label: "Proposal Sent", color: "bg-indigo-400" },
  { key: "negotiation", label: "Negotiation", color: "bg-orange-400" },
  { key: "won", label: "Won", color: "bg-green-500" },
  { key: "lost", label: "Lost", color: "bg-red-400" },
];

interface DashboardStats {
  total_leads: number;
  active_campaigns: number;
  messages_sent_week: number;
  total_sent: number;
  total_replies: number;
  response_rate: number | null;
  pipeline: Record<string, number>;
  classifications: Record<string, number>;
  active_seasons: { name: string; type: string }[];
  // CRM
  total_clients: number;
  active_orders: number;
  pipeline_value: number;
  monthly_revenue: number;
  pending_quotes: number;
  ama_distribution: Record<string, number>;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.dashboard.stats();
        setStats(data);
      } catch (err) {
        console.error("Failed to load dashboard stats:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const pipelineTotal = stats
    ? STAGE_CONFIG.reduce((sum, s) => sum + (stats.pipeline[s.key] || 0), 0)
    : 0;

  return (
    <div>
      <Header title="Dashboard" />

      {/* Overview Metrics */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <MetricCard
          label="Total Leads"
          value={loading ? "..." : String(stats?.total_leads || 0)}
          subtext="All stages"
        />
        <MetricCard
          label="Active Campaigns"
          value={loading ? "..." : String(stats?.active_campaigns || 0)}
          subtext="Running now"
        />
        <MetricCard
          label="Messages Sent"
          value={loading ? "..." : String(stats?.messages_sent_week || 0)}
          subtext="This week"
        />
        <MetricCard
          label="Response Rate"
          value={
            loading
              ? "..."
              : stats?.response_rate !== null && stats?.response_rate !== undefined
                ? `${stats.response_rate}%`
                : "--"
          }
          subtext={
            stats?.total_replies
              ? `${stats.total_replies} replies / ${stats.total_sent} sent`
              : "Awaiting data"
          }
        />
      </div>

      {/* CRM Metrics */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <MetricCard
          label="Active Clients"
          value={loading ? "..." : String(stats?.total_clients || 0)}
          subtext="CRM"
        />
        <MetricCard
          label="Active Orders"
          value={loading ? "..." : String(stats?.active_orders || 0)}
          subtext="In pipeline"
        />
        <MetricCard
          label="Pipeline Value"
          value={loading ? "..." : stats?.pipeline_value
            ? new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(stats.pipeline_value)
            : "₹0"}
          subtext="Total order value"
        />
        <MetricCard
          label="Pending Quotes"
          value={loading ? "..." : String(stats?.pending_quotes || 0)}
          subtext="Draft, sent, viewed"
        />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Pipeline */}
        <div className="col-span-2 bg-white rounded-lg p-6 shadow-sm border border-rich-creme">
          <h3 className="font-display text-xl font-bold text-crimson-dark mb-6">
            Pipeline
          </h3>
          <div className="space-y-4">
            {STAGE_CONFIG.map((stage) => {
              const count = stats?.pipeline[stage.key] || 0;
              const pct = pipelineTotal > 0 ? (count / pipelineTotal) * 100 : 0;
              return (
                <div key={stage.key} className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${stage.color}`} />
                  <span className="text-sm text-warm-charcoal w-28">{stage.label}</span>
                  <div className="flex-1 bg-creme rounded-full h-2.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${stage.color} transition-all`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="font-display font-bold text-crimson-dark w-8 text-right">
                    {loading ? "..." : count}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="bg-white rounded-lg p-6 shadow-sm border border-rich-creme">
            <h3 className="font-display text-xl font-bold text-crimson-dark mb-4">
              Quick Actions
            </h3>
            <div className="space-y-3">
              <Link
                href="/leads"
                className="block w-full px-4 py-3 bg-crimson text-creme rounded text-center text-sm font-bold hover:bg-crimson-dark transition-colors"
              >
                View Leads
              </Link>
              <Link
                href="/sequences"
                className="block w-full px-4 py-3 bg-rich-creme text-crimson-dark rounded text-center text-sm font-bold hover:bg-creme transition-colors"
              >
                Create Sequence
              </Link>
              <Link
                href="/campaigns"
                className="block w-full px-4 py-3 border border-crimson text-crimson rounded text-center text-sm font-bold hover:bg-crimson hover:text-creme transition-colors"
              >
                Create Campaign
              </Link>
              <Link
                href="/messages"
                className="block w-full px-4 py-3 border border-rich-creme text-warm-charcoal rounded text-center text-sm font-bold hover:border-crimson hover:text-crimson transition-colors"
              >
                Open Inbox
              </Link>
            </div>
            <div className="mt-3 pt-3 border-t border-rich-creme space-y-3">
              <p className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">CRM</p>
              <Link
                href="/clients"
                className="block w-full px-4 py-3 bg-rich-creme text-crimson-dark rounded text-center text-sm font-bold hover:bg-creme transition-colors"
              >
                View Clients
              </Link>
              <Link
                href="/orders"
                className="block w-full px-4 py-3 border border-crimson text-crimson rounded text-center text-sm font-bold hover:bg-crimson hover:text-creme transition-colors"
              >
                Order Pipeline
              </Link>
            </div>
          </div>

          {/* Response Classifications */}
          {stats && Object.keys(stats.classifications).length > 0 && (
            <div className="bg-white rounded-lg p-6 shadow-sm border border-rich-creme">
              <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
                Reply Classifications
              </h3>
              <div className="space-y-2">
                {Object.entries(stats.classifications).map(([cls, count]) => (
                  <div key={cls} className="flex items-center justify-between">
                    <Badge
                      variant={
                        cls === "interested" || cls === "meeting_request"
                          ? "success"
                          : cls === "not_interested" || cls === "unsubscribe"
                            ? "crimson"
                            : cls === "requesting_info"
                              ? "info"
                              : "default"
                      }
                    >
                      {cls.replace(/_/g, " ")}
                    </Badge>
                    <span className="font-display font-bold text-crimson-dark">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Active Seasons */}
          <div className="bg-white rounded-lg p-6 shadow-sm border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Active Seasons
            </h3>
            {stats && stats.active_seasons.length > 0 ? (
              <div className="space-y-2">
                {stats.active_seasons.map((season, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Badge variant={season.type === "festive" ? "warning" : season.type === "corporate" ? "info" : "default"}>
                      {season.type}
                    </Badge>
                    <span className="text-sm text-warm-charcoal">{season.name}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-mid-warm italic">
                {loading ? "Loading..." : "No active seasons right now."}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
