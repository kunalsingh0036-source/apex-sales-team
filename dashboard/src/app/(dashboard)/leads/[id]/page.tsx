"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";
import { Lead, Activity, STAGE_LABELS, LeadStage } from "@/lib/types";

const STAGES: LeadStage[] = [
  "prospect", "contacted", "engaged", "qualified",
  "proposal_sent", "negotiation", "won", "lost", "nurture",
];

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  const { toast } = useToast();
  const [lead, setLead] = useState<Lead | null>(null);
  const [timeline, setTimeline] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [leadData, timelineData] = await Promise.all([
          api.leads.get(leadId),
          api.leads.timeline(leadId),
        ]);
        setLead(leadData);
        setTimeline(timelineData);
      } catch (err) {
        console.error("Failed to load lead:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [leadId]);

  async function handleStageChange(newStage: string) {
    try {
      const updated = await api.leads.updateStage(leadId, newStage);
      setLead(updated);
      const newTimeline = await api.leads.timeline(leadId);
      setTimeline(newTimeline);
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  if (loading) {
    return (
      <div>
        <Header title="Loading..." />
        <p className="text-mid-warm">Loading lead details...</p>
      </div>
    );
  }

  if (!lead) {
    return (
      <div>
        <Header title="Lead Not Found" />
        <p className="text-mid-warm">This lead does not exist.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={() => router.back()}
          className="text-crimson hover:text-crimson-dark text-sm"
        >
          &larr; Back
        </button>
        <h2 className="font-display text-3xl font-bold text-crimson-dark">
          {lead.full_name}
        </h2>
      </div>

      <div className="grid grid-cols-3 gap-8">
        {/* Main Info */}
        <div className="col-span-2 space-y-6">
          {/* Contact Card */}
          <div className="bg-white rounded-xl p-7 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
              Contact Information
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-mid-warm">Email:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {lead.email || "—"}
                </span>
              </div>
              <div>
                <span className="text-mid-warm">Phone:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {lead.phone || "—"}
                </span>
              </div>
              <div>
                <span className="text-mid-warm">WhatsApp:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {lead.whatsapp_number || "—"}
                </span>
              </div>
              <div>
                <span className="text-mid-warm">LinkedIn:</span>{" "}
                {lead.linkedin_url ? (
                  <a
                    href={lead.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-crimson hover:underline"
                  >
                    View Profile
                  </a>
                ) : (
                  <span className="text-warm-charcoal">—</span>
                )}
              </div>
              <div>
                <span className="text-mid-warm">Instagram:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {lead.instagram_handle ? `@${lead.instagram_handle}` : "—"}
                </span>
              </div>
              <div>
                <span className="text-mid-warm">Location:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {[lead.city, lead.state, lead.country].filter(Boolean).join(", ") || "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Professional Info */}
          <div className="bg-white rounded-xl p-7 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
              Professional Details
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-mid-warm">Title:</span>{" "}
                <span className="text-warm-charcoal font-medium">{lead.job_title}</span>
              </div>
              <div>
                <span className="text-mid-warm">Department:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {lead.department || "—"}
                </span>
              </div>
              <div>
                <span className="text-mid-warm">Seniority:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {lead.seniority || "—"}
                </span>
              </div>
              <div>
                <span className="text-mid-warm">Company:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {lead.company?.name || "—"}
                </span>
              </div>
              {lead.company && (
                <>
                  <div>
                    <span className="text-mid-warm">Industry:</span>{" "}
                    <span className="text-warm-charcoal font-medium">
                      {lead.company.industry}
                    </span>
                  </div>
                  <div>
                    <span className="text-mid-warm">Company Size:</span>{" "}
                    <span className="text-warm-charcoal font-medium">
                      {lead.company.employee_count || "—"}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Timeline */}
          <div className="bg-white rounded-xl p-7 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
              Activity Timeline
            </h3>
            {timeline.length === 0 ? (
              <p className="text-sm text-mid-warm italic">No activity recorded yet.</p>
            ) : (
              <div className="space-y-4">
                {timeline.map((activity) => (
                  <div
                    key={activity.id}
                    className="flex gap-4 pb-4 border-b border-rich-creme/50 last:border-0"
                  >
                    <div className="w-2 h-2 rounded-full bg-crimson mt-2 shrink-0" />
                    <div>
                      <p className="text-sm text-warm-charcoal">
                        {activity.description}
                      </p>
                      <p className="text-xs text-mid-warm mt-1">
                        {new Date(activity.created_at).toLocaleString("en-IN")}
                        {activity.channel && ` · ${activity.channel}`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Score */}
          <div className="bg-white rounded-xl p-8 border border-rich-creme text-center">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Lead Score
            </h3>
            <div className="font-display text-6xl font-bold text-crimson-dark">
              {lead.lead_score}
            </div>
            <p className="text-xs text-mid-warm mt-1">out of 100</p>
            {lead.score_breakdown && Object.keys(lead.score_breakdown).length > 0 && (
              <div className="mt-4 space-y-2 text-left">
                {Object.entries(lead.score_breakdown).map(([key, val]) => (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-mid-warm capitalize">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className="font-bold text-warm-charcoal">{val}/25</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Stage */}
          <div className="bg-white rounded-xl p-6 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Pipeline Stage
            </h3>
            <select
              value={lead.stage}
              onChange={(e) => handleStageChange(e.target.value)}
              className="w-full px-3 py-2 border border-rich-creme rounded text-sm bg-white focus:outline-none focus:border-crimson"
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {STAGE_LABELS[s]}
                </option>
              ))}
            </select>
            {lead.deal_value && (
              <div className="mt-3">
                <span className="text-xs text-mid-warm">Deal Value: </span>
                <span className="font-display font-bold text-crimson-dark">
                  ₹{lead.deal_value.toLocaleString("en-IN")}
                </span>
              </div>
            )}
          </div>

          {/* Tags */}
          <div className="bg-white rounded-xl p-6 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Tags
            </h3>
            {lead.tags.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {lead.tags.map((tag) => (
                  <Badge key={tag} variant="default">
                    {tag}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-mid-warm italic">No tags</p>
            )}
          </div>

          {/* Meta */}
          <div className="bg-white rounded-xl p-6 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Details
            </h3>
            <div className="space-y-2 text-xs text-mid-warm">
              <div className="flex justify-between">
                <span>Source</span>
                <span className="text-warm-charcoal font-medium">{lead.source}</span>
              </div>
              <div className="flex justify-between">
                <span>Consent</span>
                <span className="text-warm-charcoal font-medium">{lead.consent_status}</span>
              </div>
              <div className="flex justify-between">
                <span>Do Not Contact</span>
                <span className="text-warm-charcoal font-medium">
                  {lead.do_not_contact ? "Yes" : "No"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Created</span>
                <span className="text-warm-charcoal font-medium">
                  {new Date(lead.created_at).toLocaleDateString("en-IN")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
