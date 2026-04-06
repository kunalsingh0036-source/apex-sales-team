"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import MetricCard from "@/components/ui/MetricCard";
import { api } from "@/lib/api-client";

const STAGE_LABELS: Record<string, string> = {
  prospect: "Prospect", contacted: "Contacted", engaged: "Engaged",
  qualified: "Qualified", proposal_sent: "Proposal Sent",
  negotiation: "Negotiation", won: "Won", lost: "Lost",
};

const STAGE_COLORS: Record<string, string> = {
  prospect: "bg-gray-400", contacted: "bg-blue-400", engaged: "bg-amber-400",
  qualified: "bg-purple-400", proposal_sent: "bg-indigo-400",
  negotiation: "bg-orange-400", won: "bg-green-500", lost: "bg-red-400",
};

const CHANNEL_COLORS: Record<string, string> = {
  email: "bg-blue-500", linkedin: "bg-sky-500",
  whatsapp: "bg-green-500", instagram: "bg-pink-500",
};

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<any>(null);
  const [funnel, setFunnel] = useState<any[]>([]);
  const [channels, setChannels] = useState<any[]>([]);
  const [campaignMetrics, setCampaignMetrics] = useState<any[]>([]);
  const [leadScores, setLeadScores] = useState<any[]>([]);
  const [aiInsights, setAiInsights] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [days, setDays] = useState(30);

  async function loadData() {
    setLoading(true);
    try {
      const [overviewData, funnelData, channelData, campaignData, scoreData] = await Promise.all([
        api.analytics.overview(days),
        api.analytics.funnel(),
        api.analytics.channels(days),
        api.analytics.campaigns(),
        api.analytics.leadScores(),
      ]);
      setOverview(overviewData);
      setFunnel(funnelData);
      setChannels(channelData);
      setCampaignMetrics(campaignData);
      setLeadScores(scoreData);
    } catch (err) {
      console.error("Analytics load failed:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [days]);

  async function handleAiInsights() {
    setLoadingInsights(true);
    try {
      const data = await api.analytics.aiInsights();
      setAiInsights(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingInsights(false);
    }
  }

  const totalFunnel = funnel.reduce((s, f) => s + f.count, 0) || 1;

  return (
    <div>
      <Header title="Analytics" />

      {/* Period selector */}
      <div className="flex items-center gap-3 mb-6">
        {[7, 14, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`text-sm px-4 py-2 rounded border transition-colors ${
              days === d
                ? "bg-crimson text-white border-crimson"
                : "border-rich-creme text-warm-charcoal hover:border-crimson"
            }`}
          >
            {d}d
          </button>
        ))}
        <span className="text-sm text-mid-warm ml-2">
          {loading ? "Loading..." : `Last ${days} days`}
        </span>
      </div>

      {/* Overview metrics */}
      {overview && (
        <div className="grid grid-cols-3 gap-6 mb-10">
          <MetricCard label="Total Sent" value={String(overview.total_sent)} />
          <MetricCard label="Total Replied" value={String(overview.total_replied)} />
          <MetricCard label="Reply Rate" value={`${overview.reply_rate}%`} accent="text-green-700" />
          <MetricCard label="Positive Replies" value={String(overview.total_positive_replies)} accent="text-green-700" />
          <MetricCard label="Meetings" value={String(overview.total_meetings)} accent="text-blue-700" />
        </div>
      )}

      <div className="grid grid-cols-3 gap-6 mb-8">
        {/* Pipeline Funnel */}
        <div className="col-span-2 bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">Pipeline Funnel</h3>
          <div className="space-y-3">
            {funnel.map((stage) => {
              const pct = (stage.count / totalFunnel) * 100;
              return (
                <div key={stage.stage} className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${STAGE_COLORS[stage.stage] || "bg-gray-400"}`} />
                  <span className="text-sm text-warm-charcoal w-28 truncate">
                    {STAGE_LABELS[stage.stage] || stage.stage}
                  </span>
                  <div className="flex-1 bg-creme rounded-full h-3 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${STAGE_COLORS[stage.stage] || "bg-gray-400"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="font-display font-bold text-crimson-dark w-12 text-right">
                    {stage.count}
                  </span>
                  <span className="text-xs text-mid-warm w-12 text-right">{stage.percentage}%</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Lead Score Distribution */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">Lead Scores</h3>
          {leadScores.length > 0 ? (
            <div className="space-y-3">
              {leadScores.map((tier) => (
                <div key={tier.tier} className="flex items-center justify-between">
                  <Badge
                    variant={
                      tier.tier === "hot" ? "crimson" :
                      tier.tier === "warm" ? "warning" :
                      tier.tier === "medium" ? "info" : "default"
                    }
                  >
                    {tier.tier}
                  </Badge>
                  <span className="font-display font-bold text-crimson-dark">{tier.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-mid-warm italic">No scored leads yet.</p>
          )}
        </div>
      </div>

      {/* Channel Comparison */}
      {channels.length > 0 && (
        <div className="bg-white rounded-xl p-6 border border-rich-creme mb-8">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">Channel Comparison</h3>
          <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-rich-creme">
                <th className="text-left px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Channel</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Sent</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Replied</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Reply Rate</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Positive</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Positive Rate</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Meetings</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Bounced</th>
              </tr>
            </thead>
            <tbody>
              {channels.map((ch) => (
                <tr key={ch.channel} className="border-b border-rich-creme/50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${CHANNEL_COLORS[ch.channel] || "bg-gray-400"}`} />
                      <span className="text-sm font-bold text-warm-charcoal capitalize">{ch.channel}</span>
                    </div>
                  </td>
                  <td className="text-right px-4 py-3 text-sm font-mono">{ch.sent}</td>
                  <td className="text-right px-4 py-3 text-sm font-mono">{ch.replied}</td>
                  <td className="text-right px-4 py-3 text-sm font-bold text-green-700">{ch.reply_rate}%</td>
                  <td className="text-right px-4 py-3 text-sm font-mono">{ch.positive_replies}</td>
                  <td className="text-right px-4 py-3 text-sm font-bold text-blue-700">{ch.positive_rate}%</td>
                  <td className="text-right px-4 py-3 text-sm font-mono">{ch.meetings}</td>
                  <td className="text-right px-4 py-3 text-sm font-mono text-red-600">{ch.bounced}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* Campaign Metrics */}
      {campaignMetrics.length > 0 && (
        <div className="bg-white rounded-xl p-6 border border-rich-creme mb-8">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">Campaign Performance</h3>
          <table className="w-full">
            <thead>
              <tr className="border-b border-rich-creme">
                <th className="text-left px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Campaign</th>
                <th className="text-left px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Status</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Enrolled</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Active</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Replied</th>
                <th className="text-right px-4 py-2 font-label text-xs tracking-wider text-mid-warm uppercase whitespace-nowrap">Reply Rate</th>
              </tr>
            </thead>
            <tbody>
              {campaignMetrics.map((c) => (
                <tr key={c.id} className="border-b border-rich-creme/50">
                  <td className="px-4 py-3 text-sm font-bold text-warm-charcoal truncate max-w-[250px]">{c.name}</td>
                  <td className="px-4 py-3">
                    <Badge variant={c.status === "active" ? "success" : c.status === "paused" ? "warning" : "default"}>
                      {c.status}
                    </Badge>
                  </td>
                  <td className="text-right px-4 py-3 text-sm font-mono">{c.enrollments}</td>
                  <td className="text-right px-4 py-3 text-sm font-mono">{c.active}</td>
                  <td className="text-right px-4 py-3 text-sm font-mono">{c.replied}</td>
                  <td className="text-right px-4 py-3 text-sm font-bold text-green-700">{c.reply_rate}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* AI Insights */}
      <div className="bg-white rounded-xl p-6 border border-rich-creme">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-lg font-bold text-crimson-dark">AI Trend Analysis</h3>
          <Button size="sm" onClick={handleAiInsights} disabled={loadingInsights}>
            {loadingInsights ? "Analyzing..." : "Generate AI Insights"}
          </Button>
        </div>

        {aiInsights ? (
          <div className="bg-creme/50 rounded-lg p-5 border-l-4 border-crimson">
            <div className="text-sm text-warm-charcoal whitespace-pre-wrap">
              {typeof aiInsights.analysis === "string"
                ? aiInsights.analysis
                : JSON.stringify(aiInsights.analysis, null, 2)}
            </div>
          </div>
        ) : (
          <p className="text-sm text-mid-warm italic">
            Click &quot;Generate AI Insights&quot; to get Claude-powered trend analysis and strategy recommendations based on your data.
          </p>
        )}
      </div>
    </div>
  );
}
