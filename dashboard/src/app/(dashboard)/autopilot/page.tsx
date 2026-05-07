"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function AutopilotPage() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [triggerLoading, setTriggerLoading] = useState<string | null>(null);
  const [savingIcp, setSavingIcp] = useState(false);
  const { toast } = useToast();
  const [savingSettings, setSavingSettings] = useState(false);

  // ICP form state
  const [icpTitles, setIcpTitles] = useState("");
  const [icpIndustries, setIcpIndustries] = useState("");
  const [icpLocations, setIcpLocations] = useState("");
  const [icpSizes, setIcpSizes] = useState("");
  const [icpMaxResults, setIcpMaxResults] = useState(50);

  // Settings form state
  const [campaignDay, setCampaignDay] = useState(0);
  const [aggressiveness, setAggressiveness] = useState("normal");

  // Batches
  const [batches, setBatches] = useState<any[]>([]);
  const [generatingBatch, setGeneratingBatch] = useState(false);
  const [selectedProfileId, setSelectedProfileId] = useState<string>(""); // "" = auto-rotate

  // Profiles (search segments — schools, hotels, banks, etc.)
  const [profiles, setProfiles] = useState<any[]>([]);
  const [editingProfile, setEditingProfile] = useState<any | null>(null);
  const [showAddProfile, setShowAddProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({
    code: "", name: "", description: "",
    job_titles: "", industries: "", locations: "India", company_sizes: "201-500, 501-1000, 1001-5000",
    keywords: "", rotation_priority: 100, is_active: true,
  });
  const [savingProfile, setSavingProfile] = useState(false);

  async function loadBatches() {
    try {
      const data = await api.batches.list(20);
      setBatches(data.batches || []);
    } catch (err) {
      console.error("batches load failed", err);
    }
  }

  async function loadProfiles() {
    try {
      const data = await api.profiles.list();
      setProfiles(data.profiles || []);
    } catch (err) {
      console.error("profiles load failed", err);
    }
  }

  function resetProfileForm() {
    setProfileForm({
      code: "", name: "", description: "",
      job_titles: "", industries: "", locations: "India", company_sizes: "201-500, 501-1000, 1001-5000",
      keywords: "", rotation_priority: 100, is_active: true,
    });
  }

  function startEditProfile(p: any) {
    setEditingProfile(p);
    setProfileForm({
      code: p.code,
      name: p.name,
      description: p.description || "",
      job_titles: (p.search_params?.job_titles || []).join(", "),
      industries: (p.search_params?.industries || []).join(", "),
      locations: (p.search_params?.locations || []).join(", "),
      company_sizes: (p.search_params?.company_sizes || []).join(", "),
      keywords: (p.search_params?.keywords || []).join(", "),
      rotation_priority: p.rotation_priority,
      is_active: p.is_active,
    });
    setShowAddProfile(true);
  }

  async function handleSaveProfile() {
    setSavingProfile(true);
    try {
      const search_params = {
        job_titles: profileForm.job_titles.split(",").map((s) => s.trim()).filter(Boolean),
        industries: profileForm.industries.split(",").map((s) => s.trim()).filter(Boolean),
        locations: profileForm.locations.split(",").map((s) => s.trim()).filter(Boolean),
        company_sizes: profileForm.company_sizes.split(",").map((s) => s.trim()).filter(Boolean),
        keywords: profileForm.keywords.split(",").map((s) => s.trim()).filter(Boolean),
      };
      if (editingProfile) {
        await api.profiles.update(editingProfile.id, {
          name: profileForm.name,
          description: profileForm.description,
          search_params,
          rotation_priority: profileForm.rotation_priority,
          is_active: profileForm.is_active,
        });
        toast(`Profile ${editingProfile.code} updated`, "success");
      } else {
        await api.profiles.create({
          code: profileForm.code,
          name: profileForm.name,
          description: profileForm.description,
          search_params,
          rotation_priority: profileForm.rotation_priority,
          is_active: profileForm.is_active,
        });
        toast(`Profile ${profileForm.code} created`, "success");
      }
      setShowAddProfile(false);
      setEditingProfile(null);
      resetProfileForm();
      await loadProfiles();
    } catch (err: any) {
      toast(err?.message || "Failed to save profile", "error");
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleToggleProfileActive(p: any) {
    try {
      await api.profiles.update(p.id, { is_active: !p.is_active });
      await loadProfiles();
    } catch (err: any) {
      toast(err?.message || "Failed to toggle profile", "error");
    }
  }

  async function handleDeleteProfile(p: any) {
    if (!confirm(`Delete profile "${p.name}"? This only works if the profile has no batches yet — otherwise mark it inactive.`)) return;
    try {
      await api.profiles.delete(p.id);
      toast(`Profile ${p.code} deleted`, "success");
      await loadProfiles();
    } catch (err: any) {
      toast(err?.message || "Failed to delete profile", "error");
    }
  }

  async function handleGenerateBatch() {
    const profileLabel = selectedProfileId
      ? profiles.find((p) => p.id === selectedProfileId)?.name || "selected profile"
      : "auto-rotated profile";
    if (!confirm(`Generate a new batch of 20 leads using ${profileLabel}? This will run discover + enrich + campaign creation.`)) return;
    setGeneratingBatch(true);
    try {
      const result = await api.batches.generate(selectedProfileId || undefined);
      const code = result?.batch?.batch_code;
      const profileName = result?.batch?.profile_name || "fallback";
      const discovered = result?.discover?.discovered ?? 0;
      toast(`Created batch ${code || "?"} (${profileName}) — discovered ${discovered} leads`, "success");
      await loadBatches();
      await loadProfiles();
      await loadData();
    } catch (err: any) {
      toast(err?.message || "Failed to generate batch", "error");
    } finally {
      setGeneratingBatch(false);
    }
  }

  async function loadData() {
    try {
      const statusData = await api.autopilot.status();
      setStatus(statusData);

      // Populate ICP form
      const icp = statusData.icp || {};
      setIcpTitles((icp.job_titles || []).join(", "));
      setIcpIndustries((icp.industries || []).join(", "));
      setIcpLocations((icp.locations || []).join(", "));
      setIcpSizes((icp.company_sizes || []).join(", "));
      setIcpMaxResults(icp.max_results || 50);

      // Populate settings
      const settings = statusData.settings || {};
      setCampaignDay(settings.campaign_day ?? 0);
      setAggressiveness(settings.aggressiveness || "normal");
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    loadBatches();
    loadProfiles();
  }, []);

  async function handleToggle() {
    if (!status) return;
    setToggling(true);
    try {
      await api.autopilot.toggle(!status.enabled);
      await loadData();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setToggling(false);
    }
  }

  async function handleTrigger(stage: string) {
    setTriggerLoading(stage);
    try {
      const result = await api.autopilot.trigger(stage);
      const labels: Record<string, string> = { discover: "Discovering new leads", enrich: "Enriching and scoring leads", sequences: "Generating sequences", campaigns: "Creating campaigns", full: "Running full pipeline" };
      toast(labels[stage] || `Running ${stage}. Refresh in a moment.`, "success");
      setTimeout(loadData, 2000);
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setTriggerLoading(null);
    }
  }

  async function handleSaveIcp() {
    setSavingIcp(true);
    try {
      await api.autopilot.updateIcp({
        job_titles: icpTitles.split(",").map((s) => s.trim()).filter(Boolean),
        industries: icpIndustries.split(",").map((s) => s.trim()).filter(Boolean),
        locations: icpLocations.split(",").map((s) => s.trim()).filter(Boolean),
        company_sizes: icpSizes.split(",").map((s) => s.trim()).filter(Boolean),
        max_results: icpMaxResults,
      });
      await loadData();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setSavingIcp(false);
    }
  }

  async function handleSaveSettings() {
    setSavingSettings(true);
    try {
      await api.autopilot.updateSettings({
        campaign_day: campaignDay,
        aggressiveness,
      });
      await loadData();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setSavingSettings(false);
    }
  }

  if (loading) {
    return (
      <div>
        <Header title="Autopilot" />
        <p className="text-mid-warm">Loading...</p>
      </div>
    );
  }

  return (
    <div>
      <Header title="Autopilot" />

      <div className="space-y-6 max-w-5xl">
        {/* Toggle */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme flex items-center justify-between">
          <div>
            <h3 className="font-display text-lg font-bold text-crimson-dark">
              Autonomous Pipeline
            </h3>
            <p className="text-sm text-mid-warm mt-1">
              Auto-discovers, enriches, scores leads and creates campaigns
            </p>
          </div>
          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`relative inline-flex h-10 w-20 items-center rounded-full transition-colors ${
              status?.enabled ? "bg-crimson" : "bg-mid-warm/30"
            } ${toggling ? "opacity-50" : ""}`}
          >
            <span
              className={`inline-block h-8 w-8 transform rounded-full bg-white shadow transition-transform ${
                status?.enabled ? "translate-x-11" : "translate-x-1"
              }`}
            />
          </button>
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-5">
          <div className="bg-white rounded-xl p-5 border border-rich-creme text-center overflow-hidden">
            <p className="font-label text-[11px] tracking-[0.12em] text-mid-warm uppercase mb-2">
              Status
            </p>
            <Badge variant={status?.enabled ? "success" : "default"}>
              {status?.enabled ? "Active" : "Disabled"}
            </Badge>
          </div>
          <div className="bg-white rounded-xl p-5 border border-rich-creme text-center overflow-hidden">
            <p className="font-label text-[11px] tracking-[0.12em] text-mid-warm uppercase mb-2">
              Leads Today
            </p>
            <p className="font-display text-2xl font-bold text-crimson-dark">
              {status?.leads_today ?? 0}
            </p>
          </div>
          <div className="bg-white rounded-xl p-5 border border-rich-creme text-center overflow-hidden">
            <p className="font-label text-[11px] tracking-[0.12em] text-mid-warm uppercase mb-2">
              In Pipeline
            </p>
            <p className="font-display text-2xl font-bold text-crimson-dark">
              {status?.pipeline ?? 0}
            </p>
          </div>
          <div className="bg-white rounded-xl p-5 border border-rich-creme text-center overflow-hidden">
            <p className="font-label text-[11px] tracking-[0.12em] text-mid-warm uppercase mb-2">
              Auto-Campaigns
            </p>
            <p className="font-display text-2xl font-bold text-crimson-dark">
              {status?.active_campaigns ?? 0}
            </p>
          </div>
        </div>

        {/* Batches — the primary tracking unit going forward */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <div className="flex items-start justify-between gap-4 mb-4 flex-col md:flex-row">
            <div>
              <h3 className="font-display text-lg font-bold text-crimson-dark">
                Lead Batches
              </h3>
              <p className="text-sm text-mid-warm mt-1">
                Each batch is a wave of up to 20 leads handled together. Auto-trigger fires every alternate day or when the prior batch is complete. Pick a profile (or let it auto-rotate) and click Generate.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={selectedProfileId}
                onChange={(e) => setSelectedProfileId(e.target.value)}
                className="px-3 py-2 border border-rich-creme rounded text-sm bg-white text-warm-charcoal focus:outline-none focus:border-crimson"
                disabled={generatingBatch}
              >
                <option value="">Auto-rotate (next in line)</option>
                {profiles.filter((p) => p.is_active).map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <Button
                size="sm"
                variant="primary"
                onClick={handleGenerateBatch}
                disabled={generatingBatch}
              >
                {generatingBatch ? "Generating..." : "Generate Next Batch (20)"}
              </Button>
            </div>
          </div>

          {batches.length === 0 ? (
            <p className="text-sm text-mid-warm italic">No batches yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-rich-creme bg-creme/40">
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Batch</th>
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Profile</th>
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Status</th>
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Triggered</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Leads</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Sent</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Replied</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Active</th>
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((b) => (
                    <tr key={b.id} className="border-b border-rich-creme/50 hover:bg-creme/30">
                      <td className="px-3 py-2 font-mono font-bold text-crimson-dark whitespace-nowrap">
                        {b.batch_code}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {b.profile ? (
                          <span className="text-warm-charcoal" title={b.profile.code}>
                            {b.profile.name}
                          </span>
                        ) : (
                          <span className="text-mid-warm italic">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={b.status === "complete" ? "success" : "default"}>
                          {b.status}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-xs text-mid-warm">
                        {b.triggered_by.replace(/_/g, " ")}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {b.actual_lead_count}/{b.target_lead_count}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{b.messages_sent}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{b.replied}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {b.active_enrollments > 0 ? (
                          <span className="text-crimson-dark font-bold">{b.active_enrollments}</span>
                        ) : (
                          <span className="text-mid-warm">0</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-mid-warm whitespace-nowrap">
                        {b.created_at ? new Date(b.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Manual Triggers */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Manual Triggers
          </h3>
          <div className="flex flex-wrap gap-3">
            {[
              { stage: "discover", label: "Discover Leads" },
              { stage: "enrich", label: "Enrich & Score" },
              { stage: "campaigns", label: "Create Campaigns" },
              { stage: "full", label: "Full Cycle" },
            ].map(({ stage, label }) => (
              <Button
                key={stage}
                size="sm"
                variant={stage === "full" ? "primary" : "secondary"}
                onClick={() => handleTrigger(stage)}
                disabled={triggerLoading !== null}
              >
                {triggerLoading === stage ? "Running..." : label}
              </Button>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Recent Activity
          </h3>
          {status?.history && status.history.length > 0 ? (
            <div className="space-y-2">
              {[...status.history].reverse().map((run: any, i: number) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-creme/50 rounded"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <Badge variant="crimson">{run.stage}</Badge>
                    <span className="text-sm text-warm-charcoal truncate">
                      {run.result?.error
                        ? `Error: ${run.result.error}`
                        : run.stage === "discover"
                        ? `${run.result?.discovered ?? 0} discovered, ${run.result?.skipped ?? 0} skipped`
                        : run.stage === "enrich"
                        ? `${run.result?.enriched ?? 0} enriched`
                        : run.stage === "sequences"
                        ? `${run.result?.created ?? 0} created, ${run.result?.checked ?? 0} checked`
                        : run.stage === "campaigns"
                        ? `${run.result?.campaigns_created ?? 0} campaigns, ${run.result?.leads_enrolled ?? 0} enrolled`
                        : JSON.stringify(run.result).slice(0, 80)}
                    </span>
                  </div>
                  <span className="text-xs text-mid-warm">
                    {new Date(run.timestamp).toLocaleString("en-IN", {
                      timeZone: "Asia/Kolkata",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-mid-warm">No runs yet. Trigger a stage above to get started.</p>
          )}
        </div>

        {/* Profiles — segments that batches rotate through */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <div className="flex items-start justify-between gap-4 mb-4 flex-col md:flex-row">
            <div>
              <h3 className="font-display text-lg font-bold text-crimson-dark">
                Lead Profiles
              </h3>
              <p className="text-sm text-mid-warm mt-1">
                Each profile defines a segment (Schools, Hotels, Pharma, etc.). Batches rotate through active profiles round-robin so every wave hits a fresh pool. Add your own profiles below — they enter rotation automatically once active.
              </p>
            </div>
            <Button
              size="sm"
              variant="primary"
              onClick={() => { setEditingProfile(null); resetProfileForm(); setShowAddProfile(true); }}
            >
              + Add Profile
            </Button>
          </div>

          {profiles.length === 0 ? (
            <p className="text-sm text-mid-warm italic">No profiles yet. Add one above.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-rich-creme bg-creme/40">
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Profile</th>
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Status</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Batches</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Leads</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Sent</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Replied</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Reply %</th>
                    <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Last Used</th>
                    <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {profiles.map((p) => (
                    <tr key={p.id} className="border-b border-rich-creme/50 hover:bg-creme/30">
                      <td className="px-3 py-2">
                        <p className="font-bold text-warm-charcoal">{p.name}</p>
                        <p className="text-[10px] text-mid-warm font-mono">{p.code}</p>
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => handleToggleProfileActive(p)}
                          className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                            p.is_active
                              ? "bg-green-100 text-green-900 hover:bg-green-200"
                              : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                          }`}
                        >
                          {p.is_active ? "ACTIVE" : "INACTIVE"}
                        </button>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{p.stats?.batches_run ?? 0}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{p.stats?.leads_generated ?? 0}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{p.stats?.messages_sent ?? 0}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{p.stats?.replied ?? 0}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {p.stats?.response_rate !== null && p.stats?.response_rate !== undefined
                          ? `${p.stats.response_rate}%`
                          : "—"}
                      </td>
                      <td className="px-3 py-2 text-xs text-mid-warm whitespace-nowrap">
                        {p.last_used_at
                          ? new Date(p.last_used_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
                          : "Never"}
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button
                          onClick={() => startEditProfile(p)}
                          className="text-xs text-crimson hover:text-crimson-dark mr-3"
                        >
                          Edit
                        </button>
                        {p.stats?.batches_run === 0 && (
                          <button
                            onClick={() => handleDeleteProfile(p)}
                            className="text-xs text-red-600 hover:text-red-800"
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Add/Edit Profile Modal */}
        {showAddProfile && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
            <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
              <h2 className="font-display text-xl font-bold text-crimson-dark mb-4">
                {editingProfile ? `Edit Profile · ${editingProfile.code}` : "Add Profile"}
              </h2>
              <div className="space-y-3">
                {!editingProfile && (
                  <div>
                    <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Code (lowercase, dashes)</label>
                    <input
                      value={profileForm.code}
                      onChange={(e) => setProfileForm({ ...profileForm, code: e.target.value })}
                      placeholder="P-airlines-aviation"
                      className="w-full px-3 py-2 border border-rich-creme rounded text-sm font-mono"
                    />
                  </div>
                )}
                <div>
                  <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Name</label>
                  <input
                    value={profileForm.name}
                    onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                    placeholder="Airlines & Aviation"
                    className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                  />
                </div>
                <div>
                  <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Description</label>
                  <textarea
                    value={profileForm.description}
                    onChange={(e) => setProfileForm({ ...profileForm, description: e.target.value })}
                    rows={2}
                    placeholder="What this segment targets and why"
                    className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                  />
                </div>
                <div>
                  <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Job Titles (comma-separated)</label>
                  <textarea
                    value={profileForm.job_titles}
                    onChange={(e) => setProfileForm({ ...profileForm, job_titles: e.target.value })}
                    rows={2}
                    placeholder="HR Director, Procurement Manager, …"
                    className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                  />
                </div>
                <div>
                  <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Industries (comma-separated)</label>
                  <textarea
                    value={profileForm.industries}
                    onChange={(e) => setProfileForm({ ...profileForm, industries: e.target.value })}
                    rows={2}
                    placeholder="Airlines/Aviation, Aviation & Aerospace"
                    className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Locations</label>
                    <input
                      value={profileForm.locations}
                      onChange={(e) => setProfileForm({ ...profileForm, locations: e.target.value })}
                      className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                    />
                  </div>
                  <div>
                    <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Company Sizes</label>
                    <input
                      value={profileForm.company_sizes}
                      onChange={(e) => setProfileForm({ ...profileForm, company_sizes: e.target.value })}
                      className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Keywords (optional)</label>
                  <input
                    value={profileForm.keywords}
                    onChange={(e) => setProfileForm({ ...profileForm, keywords: e.target.value })}
                    placeholder="airline, aviation"
                    className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-center">
                  <div>
                    <label className="font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase block mb-1">Rotation Priority (lower = picked first)</label>
                    <input
                      type="number"
                      value={profileForm.rotation_priority}
                      onChange={(e) => setProfileForm({ ...profileForm, rotation_priority: parseInt(e.target.value) || 100 })}
                      className="w-32 px-3 py-2 border border-rich-creme rounded text-sm"
                    />
                  </div>
                  <label className="flex items-center gap-2 text-sm text-warm-charcoal">
                    <input
                      type="checkbox"
                      checked={profileForm.is_active}
                      onChange={(e) => setProfileForm({ ...profileForm, is_active: e.target.checked })}
                      className="w-4 h-4 accent-crimson"
                    />
                    Active (enters rotation)
                  </label>
                </div>
                <div className="flex justify-end gap-2 pt-2 border-t border-rich-creme">
                  <Button variant="outline" size="sm" onClick={() => { setShowAddProfile(false); setEditingProfile(null); resetProfileForm(); }}>
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleSaveProfile} disabled={savingProfile || !profileForm.name || (!editingProfile && !profileForm.code)}>
                    {savingProfile ? "Saving..." : (editingProfile ? "Save Changes" : "Create Profile")}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Settings */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Autopilot Settings
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-6">
            <div>
              <label className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase block mb-1">
                Campaign Creation Day
              </label>
              <select
                value={campaignDay}
                onChange={(e) => setCampaignDay(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm text-warm-charcoal focus:outline-none focus:border-crimson bg-white"
              >
                {DAY_LABELS.map((label, i) => (
                  <option key={i} value={i}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase block mb-1">
                Aggressiveness
              </label>
              <select
                value={aggressiveness}
                onChange={(e) => setAggressiveness(e.target.value)}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm text-warm-charcoal focus:outline-none focus:border-crimson bg-white"
              >
                <option value="low">Low (25 leads/day, skip cold)</option>
                <option value="normal">Normal (50 leads/day)</option>
                <option value="high">High (100 leads/day)</option>
              </select>
            </div>
          </div>
          <div className="mt-4">
            <Button onClick={handleSaveSettings} disabled={savingSettings}>
              {savingSettings ? "Saving..." : "Save Settings"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
