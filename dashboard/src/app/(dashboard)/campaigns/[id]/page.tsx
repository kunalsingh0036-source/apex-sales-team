"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";
import { Lead } from "@/lib/types";

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id as string;

  const [campaign, setCampaign] = useState<any>(null);
  const [enrollments, setEnrollments] = useState<any[]>([]);
  const [availableLeads, setAvailableLeads] = useState<Lead[]>([]);
  const [selectedLeads, setSelectedLeads] = useState<string[]>([]);
  const { toast } = useToast();
  const [showEnroll, setShowEnroll] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [campaignData, enrollData] = await Promise.all([
          api.campaigns.get(campaignId),
          api.campaigns.enrollments(campaignId),
        ]);
        setCampaign(campaignData);
        setEnrollments(enrollData.items);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [campaignId]);

  async function loadLeads() {
    const data = await api.leads.list({ per_page: 100 });
    setAvailableLeads(data.items);
    setShowEnroll(true);
  }

  async function handleEnroll() {
    if (selectedLeads.length === 0) return;
    try {
      const result = await api.campaigns.enroll(campaignId, selectedLeads);
      toast(`Enrolled ${result.enrolled} leads. Skipped ${result.skipped}.`, "success");
      setShowEnroll(false);
      setSelectedLeads([]);
      // Refresh
      const [campaignData, enrollData] = await Promise.all([
        api.campaigns.get(campaignId),
        api.campaigns.enrollments(campaignId),
      ]);
      setCampaign(campaignData);
      setEnrollments(enrollData.items);
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  if (loading) return <div><Header title="Loading..." /></div>;
  if (!campaign) return <div><Header title="Campaign Not Found" /></div>;

  const statusCounts = enrollments.reduce(
    (acc: Record<string, number>, e: any) => {
      acc[e.status] = (acc[e.status] || 0) + 1;
      return acc;
    },
    {}
  );

  return (
    <div>
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => router.back()} className="text-crimson hover:text-crimson-dark text-sm">
          &larr; Back
        </button>
        <h2 className="font-display text-3xl font-bold text-crimson-dark">
          {campaign.name}
        </h2>
        <Badge variant={campaign.status === "active" ? "success" : "default"}>
          {campaign.status}
        </Badge>
      </div>

      {/* Campaign info */}
      <div className="bg-white rounded-xl p-6 border border-rich-creme mb-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          {campaign.started_at && (
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Started</span>
              <span className="font-bold text-warm-charcoal">
                {new Date(campaign.started_at).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric" })}
              </span>
            </div>
          )}
          {campaign.completed_at && (
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Completed</span>
              <span className="font-bold text-warm-charcoal">
                {new Date(campaign.completed_at).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric" })}
              </span>
            </div>
          )}
          {campaign.target_filter?.industry && (
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Target Industry</span>
              <span className="font-bold text-warm-charcoal">{campaign.target_filter.industry}</span>
            </div>
          )}
          {campaign.target_filter?.tier && (
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Lead Tier</span>
              <Badge variant={campaign.target_filter.tier === "hot" ? "crimson" : campaign.target_filter.tier === "warm" ? "warning" : "default"}>
                {campaign.target_filter.tier}
              </Badge>
            </div>
          )}
          {campaign.target_filter?.channel && (
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Channel</span>
              <span className="font-bold text-warm-charcoal capitalize">{campaign.target_filter.channel}</span>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-5 mb-8">
        <div className="bg-white rounded-xl p-5 border border-rich-creme text-center">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Enrolled</p>
          <p className="font-display text-2xl font-bold text-crimson-dark">{campaign.total_leads}</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-rich-creme text-center">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Active</p>
          <p className="font-display text-2xl font-bold text-green-700">{statusCounts.active || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-rich-creme text-center">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Replied</p>
          <p className="font-display text-2xl font-bold text-blue-700">{statusCounts.replied || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-rich-creme text-center">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Done</p>
          <p className="font-display text-2xl font-bold text-mid-warm">{statusCounts.completed || 0}</p>
        </div>
      </div>

      {/* Sequence info */}
      {campaign.sequence && (
        <div className="bg-white rounded-xl p-6 border border-rich-creme mb-6">
          <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">
            Sequence: {campaign.sequence.name}
          </h3>
          <div className="flex items-center gap-2">
            {campaign.sequence.steps?.map((step: any, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <div className="px-3 py-1.5 bg-creme rounded text-xs text-warm-charcoal font-bold">
                  Step {step.step_number || i + 1}
                  {step.delay_days > 0 && (
                    <span className="text-mid-warm font-normal ml-1">+{step.delay_days}d</span>
                  )}
                </div>
                {i < (campaign.sequence.steps?.length || 0) - 1 && (
                  <span className="text-rich-creme">→</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Enroll leads */}
      <div className="flex gap-3 mb-6">
        <Button size="sm" onClick={loadLeads}>
          + Enroll Leads
        </Button>
      </div>

      {showEnroll && (
        <div className="bg-white rounded-xl p-6 border border-rich-creme mb-6">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Select Leads to Enroll
          </h3>
          <div className="max-h-60 overflow-y-auto space-y-2 mb-4">
            {availableLeads.map((lead) => (
              <label key={lead.id} className="flex items-center gap-3 p-2 hover:bg-creme/50 rounded cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedLeads.includes(lead.id)}
                  onChange={(e) => {
                    setSelectedLeads(
                      e.target.checked
                        ? [...selectedLeads, lead.id]
                        : selectedLeads.filter((id) => id !== lead.id)
                    );
                  }}
                />
                <span className="text-sm font-bold text-warm-charcoal">{lead.full_name}</span>
                <span className="text-xs text-mid-warm">{lead.job_title}</span>
                <span className="text-xs text-mid-warm">{lead.company?.name || ""}</span>
              </label>
            ))}
          </div>
          <div className="flex gap-3">
            <Button size="sm" onClick={handleEnroll} disabled={selectedLeads.length === 0}>
              Enroll {selectedLeads.length} Lead{selectedLeads.length !== 1 ? "s" : ""}
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowEnroll(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Enrollments table */}
      {enrollments.length > 0 && (
        <div className="bg-white rounded-xl border border-rich-creme overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-rich-creme bg-creme/50">
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">#</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Lead</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Company</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Score</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Step</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Status</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Next Step At</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Enrolled</th>
              </tr>
            </thead>
            <tbody>
              {enrollments.map((e: any) => (
                <tr key={e.id} className="border-b border-rich-creme/50 hover:bg-creme/30">
                  <td className="px-5 py-3.5 font-mono text-xs font-bold text-crimson-dark whitespace-nowrap">
                    {e.lead?.lead_code || "—"}
                  </td>
                  <td className="px-5 py-3.5">
                    {e.lead ? (
                      <div>
                        <a href={`/leads/${e.lead.id}`} className="text-sm font-bold text-crimson-dark hover:text-crimson">
                          {e.lead.full_name}
                        </a>
                        <p className="text-xs text-mid-warm">{e.lead.job_title}</p>
                        {e.lead.email && (
                          <p className="text-xs text-mid-warm/70">{e.lead.email}</p>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-mid-warm font-mono">{e.lead_id.substring(0, 12)}...</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-sm text-warm-charcoal">
                    {e.lead?.company_name || "—"}
                  </td>
                  <td className="px-5 py-3.5">
                    {e.lead ? (
                      <span className={`text-sm font-bold ${
                        e.lead.lead_score >= 80 ? "text-green-700" :
                        e.lead.lead_score >= 60 ? "text-yellow-600" :
                        e.lead.lead_score >= 40 ? "text-orange-500" :
                        "text-mid-warm"
                      }`}>
                        {e.lead.lead_score}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="px-5 py-3.5 text-sm text-warm-charcoal">
                    Step {e.current_step + 1}
                  </td>
                  <td className="px-5 py-3.5">
                    <Badge variant={e.status === "active" ? "success" : e.status === "replied" ? "info" : "default"}>
                      {e.status}
                    </Badge>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-mid-warm">
                    {e.next_step_at
                      ? new Date(e.next_step_at).toLocaleString("en-IN", {
                          timeZone: "Asia/Kolkata",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-mid-warm">
                    {new Date(e.enrolled_at).toLocaleDateString("en-IN", {
                      timeZone: "Asia/Kolkata",
                      month: "short",
                      day: "numeric",
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {enrollments.length === 0 && !loading && (
        <div className="bg-white rounded-xl p-12 text-center border border-rich-creme">
          <p className="font-display text-xl text-crimson-dark mb-2">No leads enrolled yet</p>
          <p className="text-mid-warm text-sm">Click &quot;Enroll Leads&quot; above to add leads to this campaign.</p>
        </div>
      )}
    </div>
  );
}
