"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";
import { STAGE_LABELS, LeadStage } from "@/lib/types";

const STAGES: LeadStage[] = [
  "prospect", "contacted", "engaged", "qualified",
  "proposal_sent", "negotiation", "won", "lost", "nurture",
];

type Enrollment = {
  id: string;
  campaign_id: string;
  campaign_name: string;
  sequence_id: string;
  sequence_name: string;
  status: string;
  current_step: number;
  total_steps: number;
  next_step_at: string | null;
  next_step_channel: string | null;
  next_step_type: string | null;
  last_step_at: string | null;
  enrolled_at: string | null;
};

type ProfileMessage = {
  id: string;
  channel: string;
  direction: string;
  subject: string | null;
  body: string;
  status: string;
  classification: string | null;
  external_id: string | null;
  extra_data: {
    linkedin_type?: string;
    linkedin_status?: string;
    last_error?: string | null;
    needs_linkedin_url?: boolean;
    attachments?: { filename: string; size: number; content_type: string }[];
  };
  scheduled_at: string | null;
  sent_at: string | null;
  created_at: string;
};

type ProfileActivity = {
  id: string;
  type: string;
  channel: string | null;
  description: string;
  metadata: any;
  created_at: string;
};

type ProfileLead = {
  id: string;
  lead_number: number;
  lead_code: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  whatsapp_number: string | null;
  linkedin_url: string | null;
  job_title: string;
  department: string | null;
  seniority: string | null;
  city: string | null;
  state: string | null;
  country: string;
  source: string;
  lead_score: number;
  stage: string;
  tags: string[];
  notes: string;
  consent_status: string;
  do_not_contact: boolean;
  last_contacted_at: string | null;
  company: { id: string; name: string; domain: string | null; industry: string; employee_count: string | null } | null;
};

type Profile = {
  lead: ProfileLead;
  enrollments: Enrollment[];
  messages: ProfileMessage[];
  activities: ProfileActivity[];
};

function channelIcon(channel: string | null | undefined): string {
  if (channel === "email") return "✉";
  if (channel === "linkedin") return "in";
  if (channel === "whatsapp") return "⌾";
  if (channel === "instagram") return "◎";
  return "•";
}

function humanDelta(iso: string): string {
  const target = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = target - now;
  const abs = Math.abs(diffMs);
  const h = Math.floor(abs / (1000 * 60 * 60));
  const d = Math.floor(h / 24);
  const prefix = diffMs < 0 ? "ago" : "in";
  if (d >= 1) return `${prefix === "in" ? "in" : ""} ${d} day${d > 1 ? "s" : ""}${prefix === "ago" ? " ago" : ""}`;
  if (h >= 1) return `${prefix === "in" ? "in" : ""} ${h}h${prefix === "ago" ? " ago" : ""}`;
  const m = Math.floor(abs / (1000 * 60));
  return `${prefix === "in" ? "in" : ""} ${m}m${prefix === "ago" ? " ago" : ""}`;
}

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  const { toast } = useToast();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProfile = useCallback(async () => {
    try {
      const data = await api.leads.profile(leadId);
      setProfile(data);
    } catch (err) {
      console.error("Failed to load lead profile:", err);
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  async function handleStageChange(newStage: string) {
    try {
      await api.leads.updateStage(leadId, newStage);
      await loadProfile();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleMarkLinkedinStatus(messageId: string, status: "accepted" | "declined") {
    try {
      await api.messages.markLinkedinStatus(messageId, status);
      toast(`Marked as ${status}.`, "success");
      await loadProfile();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  // Merge messages + activities into a single chronological timeline
  const timelineItems = useMemo(() => {
    if (!profile) return [];
    const items: Array<{ kind: "message" | "activity"; ts: number; data: any }> = [];
    for (const m of profile.messages) {
      items.push({ kind: "message", ts: new Date(m.sent_at || m.created_at).getTime(), data: m });
    }
    for (const a of profile.activities) {
      // Skip activities that duplicate a message (e.g. "email_queued" right before the actual send)
      if (a.type?.endsWith("_queued") || a.type?.endsWith("_sent")) continue;
      items.push({ kind: "activity", ts: new Date(a.created_at).getTime(), data: a });
    }
    items.sort((a, b) => b.ts - a.ts);
    return items;
  }, [profile]);

  // Find most recent LinkedIn message for the LinkedIn status card
  const linkedinMessage = useMemo(() => {
    if (!profile) return null;
    const ln = profile.messages.filter((m) => m.channel === "linkedin" && m.direction === "outbound");
    if (ln.length === 0) return null;
    // Prefer sent over queued/content_review
    const sent = ln.find((m) => m.status === "sent");
    return sent || ln[0];
  }, [profile]);

  if (loading) {
    return (
      <div>
        <Header title="Loading..." />
        <p className="text-mid-warm">Loading lead profile...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div>
        <Header title="Lead Not Found" />
        <p className="text-mid-warm">This lead does not exist or could not be loaded.</p>
      </div>
    );
  }

  const { lead } = profile;

  return (
    <div>
      <div className="flex items-center gap-4 mb-6 md:mb-8">
        <button
          onClick={() => router.back()}
          className="text-crimson hover:text-crimson-dark text-sm"
        >
          &larr; Back
        </button>
        <h2 className="font-display text-2xl md:text-3xl font-bold text-crimson-dark break-words">
          {lead.full_name}
          {lead.lead_code && (
            <span className="ml-3 font-mono text-base md:text-lg text-mid-warm font-normal">· {lead.lead_code}</span>
          )}
        </h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-5">
          {/* Contact Card */}
          <div className="bg-white rounded-xl p-5 md:p-7 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
              Contact Information
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-mid-warm">Email:</span>{" "}
                <span className="text-warm-charcoal font-medium break-all">{lead.email || "—"}</span>
              </div>
              <div>
                <span className="text-mid-warm">Phone:</span>{" "}
                <span className="text-warm-charcoal font-medium">{lead.phone || "—"}</span>
              </div>
              <div>
                <span className="text-mid-warm">WhatsApp:</span>{" "}
                <span className="text-warm-charcoal font-medium">{lead.whatsapp_number || "—"}</span>
              </div>
              <div>
                <span className="text-mid-warm">LinkedIn:</span>{" "}
                {lead.linkedin_url ? (
                  <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-crimson hover:underline break-all">
                    View Profile
                  </a>
                ) : (
                  <span className="text-red-700 italic">Missing</span>
                )}
              </div>
              <div className="md:col-span-2">
                <span className="text-mid-warm">Location:</span>{" "}
                <span className="text-warm-charcoal font-medium">
                  {[lead.city, lead.state, lead.country].filter(Boolean).join(", ") || "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Professional Info */}
          <div className="bg-white rounded-xl p-5 md:p-7 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
              Professional Details
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-mid-warm">Title:</span>{" "}
                <span className="text-warm-charcoal font-medium">{lead.job_title}</span>
              </div>
              <div>
                <span className="text-mid-warm">Department:</span>{" "}
                <span className="text-warm-charcoal font-medium">{lead.department || "—"}</span>
              </div>
              <div>
                <span className="text-mid-warm">Seniority:</span>{" "}
                <span className="text-warm-charcoal font-medium">{lead.seniority || "—"}</span>
              </div>
              <div>
                <span className="text-mid-warm">Company:</span>{" "}
                <span className="text-warm-charcoal font-medium">{lead.company?.name || "—"}</span>
              </div>
              {lead.company && (
                <>
                  <div>
                    <span className="text-mid-warm">Industry:</span>{" "}
                    <span className="text-warm-charcoal font-medium">{lead.company.industry}</span>
                  </div>
                  <div>
                    <span className="text-mid-warm">Company Size:</span>{" "}
                    <span className="text-warm-charcoal font-medium">{lead.company.employee_count || "—"}</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Active Enrollments */}
          {profile.enrollments.length > 0 && (
            <div className="bg-white rounded-xl p-5 md:p-7 border border-rich-creme">
              <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
                Sequence Enrollments
              </h3>
              <div className="space-y-4">
                {profile.enrollments.map((enr) => {
                  const pct = enr.total_steps ? Math.round((enr.current_step / enr.total_steps) * 100) : 0;
                  const statusColor: Record<string, "success" | "warning" | "info" | "default"> = {
                    active: "success",
                    paused: "warning",
                    replied: "info",
                    completed: "default",
                  };
                  return (
                    <div key={enr.id} className="border border-rich-creme/60 rounded-lg p-4">
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-warm-charcoal truncate">{enr.campaign_name}</p>
                          <p className="text-xs text-mid-warm">{enr.sequence_name}</p>
                        </div>
                        <Badge variant={statusColor[enr.status] || "default"}>{enr.status}</Badge>
                      </div>
                      <div className="text-xs text-mid-warm mb-2">
                        Step {Math.min(enr.current_step + 1, enr.total_steps)} of {enr.total_steps}
                      </div>
                      <div className="h-2 bg-creme rounded-full overflow-hidden mb-3">
                        <div className="h-full bg-crimson" style={{ width: `${pct}%` }} />
                      </div>
                      {enr.status === "active" && enr.next_step_at && enr.next_step_channel && (
                        <p className="text-xs text-warm-charcoal">
                          Next: <span className="font-bold">{channelIcon(enr.next_step_channel)} {enr.next_step_type?.replace(/_/g, " ")}</span>{" "}
                          <span className="text-mid-warm">({humanDelta(enr.next_step_at)})</span>
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* LinkedIn Status */}
          {linkedinMessage && (
            <div className="bg-white rounded-xl p-5 md:p-7 border border-rich-creme">
              <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
                LinkedIn Status
              </h3>
              {(() => {
                const lnStatus = linkedinMessage.extra_data?.linkedin_status || "pending_approval";
                const label: Record<string, { text: string; color: string }> = {
                  pending_approval: { text: "Pending approval", color: "bg-gray-200 text-gray-800" },
                  queued: { text: "Queued to send", color: "bg-blue-100 text-blue-800" },
                  sent: { text: "Sent — awaiting response", color: "bg-amber-100 text-amber-900" },
                  accepted: { text: "Accepted", color: "bg-green-100 text-green-900" },
                  declined: { text: "Declined / ignored", color: "bg-red-100 text-red-900" },
                  failed: { text: "Failed to send", color: "bg-red-100 text-red-900" },
                };
                const badge = label[lnStatus] || label.pending_approval;
                const sentDate = linkedinMessage.sent_at ? new Date(linkedinMessage.sent_at).toLocaleDateString("en-IN") : null;
                return (
                  <>
                    <div className="flex items-center gap-3 mb-3 flex-wrap">
                      <span className={`text-xs font-bold px-3 py-1 rounded-full ${badge.color}`}>{badge.text}</span>
                      {sentDate && <span className="text-xs text-mid-warm">Sent {sentDate}</span>}
                    </div>
                    <div className="bg-creme/40 rounded p-3 text-sm text-warm-charcoal whitespace-pre-wrap mb-3 max-h-32 overflow-y-auto">
                      {linkedinMessage.body || <span className="italic text-mid-warm">No body</span>}
                    </div>
                    {lnStatus === "sent" && (
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => handleMarkLinkedinStatus(linkedinMessage.id, "accepted")}>
                          Mark Accepted
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleMarkLinkedinStatus(linkedinMessage.id, "declined")}>
                          Mark Declined
                        </Button>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          )}

          {/* Unified Outreach Timeline */}
          <div className="bg-white rounded-xl p-5 md:p-7 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-4">
              Outreach Timeline
            </h3>
            {timelineItems.length === 0 ? (
              <p className="text-sm text-mid-warm italic">No outreach activity yet.</p>
            ) : (
              <div className="space-y-0">
                {timelineItems.map((item) => {
                  if (item.kind === "message") {
                    const m: ProfileMessage = item.data;
                    const isInbound = m.direction === "inbound";
                    const statusColor: Record<string, string> = {
                      sent: "bg-green-100 text-green-900",
                      content_review: "bg-amber-100 text-amber-900",
                      queued: "bg-blue-100 text-blue-900",
                      failed: "bg-red-100 text-red-900",
                      received: "bg-purple-100 text-purple-900",
                      draft: "bg-gray-200 text-gray-800",
                    };
                    return (
                      <div key={`m-${m.id}`} className="flex gap-3 pb-4 border-b border-rich-creme/40 last:border-0 pt-4 first:pt-0">
                        <div className="shrink-0 w-8 h-8 rounded-full bg-creme flex items-center justify-center text-sm font-bold text-crimson-dark">
                          {channelIcon(m.channel)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span className="text-xs font-bold uppercase tracking-wider text-mid-warm">{m.channel}</span>
                            <span className="text-xs text-mid-warm">{isInbound ? "← inbound" : "→ outbound"}</span>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${statusColor[m.status] || "bg-gray-200 text-gray-800"}`}>
                              {m.status}
                            </span>
                            {m.extra_data?.linkedin_status && m.extra_data.linkedin_status !== m.status && (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-crimson/10 text-crimson-dark">
                                LN: {m.extra_data.linkedin_status}
                              </span>
                            )}
                            {m.classification && (
                              <Badge variant={m.classification === "interested" || m.classification === "meeting_request" ? "success" : m.classification === "not_interested" || m.classification === "unsubscribe" ? "crimson" : "default"}>
                                {m.classification.replace(/_/g, " ")}
                              </Badge>
                            )}
                          </div>
                          {m.subject && <p className="text-sm font-bold text-warm-charcoal break-words">{m.subject}</p>}
                          <p className="text-sm text-warm-charcoal mt-1 whitespace-pre-wrap line-clamp-3">{m.body}</p>
                          <p className="text-xs text-mid-warm mt-1">
                            {new Date(m.sent_at || m.created_at).toLocaleString("en-IN")}
                          </p>
                          {m.extra_data?.last_error && (
                            <p className="text-xs text-red-700 mt-1 italic">⚠ {m.extra_data.last_error}</p>
                          )}
                        </div>
                      </div>
                    );
                  }
                  // activity
                  const a: ProfileActivity = item.data;
                  return (
                    <div key={`a-${a.id}`} className="flex gap-3 pb-4 border-b border-rich-creme/40 last:border-0 pt-4 first:pt-0">
                      <div className="shrink-0 w-8 h-8 rounded-full bg-crimson/10 flex items-center justify-center text-xs text-crimson-dark">
                        ⚡
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm text-warm-charcoal">{a.description}</p>
                        <p className="text-xs text-mid-warm mt-1">
                          {new Date(a.created_at).toLocaleString("en-IN")}
                          {a.channel && ` · ${a.channel}`}
                          <span className="ml-2 text-mid-warm/70">{a.type}</span>
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-5">
          {/* Score */}
          <div className="bg-white rounded-xl p-6 md:p-8 border border-rich-creme text-center">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Lead Score
            </h3>
            <div className="font-display text-5xl md:text-6xl font-bold text-crimson-dark">
              {lead.lead_score}
            </div>
            <p className="text-xs text-mid-warm mt-1">out of 100</p>
          </div>

          {/* Stage */}
          <div className="bg-white rounded-xl p-5 md:p-6 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Pipeline Stage
            </h3>
            <select
              value={lead.stage}
              onChange={(e) => handleStageChange(e.target.value)}
              className="w-full px-3 py-2 border border-rich-creme rounded text-sm bg-white focus:outline-none focus:border-crimson"
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>{STAGE_LABELS[s]}</option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div className="bg-white rounded-xl p-5 md:p-6 border border-rich-creme">
            <h3 className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-3">
              Tags
            </h3>
            {lead.tags.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {lead.tags.map((tag) => (
                  <Badge key={tag} variant="default">{tag}</Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-mid-warm italic">No tags</p>
            )}
          </div>

          {/* Meta */}
          <div className="bg-white rounded-xl p-5 md:p-6 border border-rich-creme">
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
                <span className="text-warm-charcoal font-medium">{lead.do_not_contact ? "Yes" : "No"}</span>
              </div>
              <div className="flex justify-between">
                <span>Last Contacted</span>
                <span className="text-warm-charcoal font-medium">
                  {lead.last_contacted_at ? new Date(lead.last_contacted_at).toLocaleDateString("en-IN") : "Never"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
