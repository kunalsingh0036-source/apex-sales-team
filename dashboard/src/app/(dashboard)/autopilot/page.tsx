"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function AutopilotPage() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [triggerLoading, setTriggerLoading] = useState<string | null>(null);
  const [savingIcp, setSavingIcp] = useState(false);
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
  }, []);

  async function handleToggle() {
    if (!status) return;
    setToggling(true);
    try {
      await api.autopilot.toggle(!status.enabled);
      await loadData();
    } catch (err: any) {
      alert("Toggle failed: " + err.message);
    } finally {
      setToggling(false);
    }
  }

  async function handleTrigger(stage: string) {
    setTriggerLoading(stage);
    try {
      const result = await api.autopilot.trigger(stage);
      const labels: Record<string, string> = { discover: "Discovering new leads", enrich: "Enriching and scoring leads", sequences: "Generating sequences", campaigns: "Creating campaigns", full: "Running full pipeline" };
      alert(labels[stage] || `Running ${stage}. Refresh in a moment.`);
      setTimeout(loadData, 2000);
    } catch (err: any) {
      alert("Trigger failed: " + err.message);
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
      alert("Save failed: " + err.message);
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
      alert("Save failed: " + err.message);
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
        <div className="grid grid-cols-2 gap-5">
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

        {/* ICP Editor */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Ideal Customer Profile
          </h3>
          <div className="space-y-4">
            <div>
              <label className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase block mb-1">
                Job Titles (comma-separated)
              </label>
              <textarea
                value={icpTitles}
                onChange={(e) => setIcpTitles(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm text-warm-charcoal focus:outline-none focus:border-crimson"
              />
            </div>
            <div>
              <label className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase block mb-1">
                Industries (comma-separated)
              </label>
              <textarea
                value={icpIndustries}
                onChange={(e) => setIcpIndustries(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm text-warm-charcoal focus:outline-none focus:border-crimson"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase block mb-1">
                  Locations
                </label>
                <input
                  value={icpLocations}
                  onChange={(e) => setIcpLocations(e.target.value)}
                  className="w-full px-3 py-2 border border-rich-creme rounded text-sm text-warm-charcoal focus:outline-none focus:border-crimson"
                />
              </div>
              <div>
                <label className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase block mb-1">
                  Company Sizes
                </label>
                <input
                  value={icpSizes}
                  onChange={(e) => setIcpSizes(e.target.value)}
                  className="w-full px-3 py-2 border border-rich-creme rounded text-sm text-warm-charcoal focus:outline-none focus:border-crimson"
                />
              </div>
            </div>
            <div className="flex items-end gap-4">
              <div>
                <label className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase block mb-1">
                  Max Leads / Day
                </label>
                <input
                  type="number"
                  value={icpMaxResults}
                  onChange={(e) => setIcpMaxResults(parseInt(e.target.value) || 50)}
                  min={10}
                  max={100}
                  className="w-32 px-3 py-2 border border-rich-creme rounded text-sm text-warm-charcoal focus:outline-none focus:border-crimson"
                />
              </div>
              <Button onClick={handleSaveIcp} disabled={savingIcp}>
                {savingIcp ? "Saving..." : "Save ICP"}
              </Button>
            </div>
          </div>
        </div>

        {/* Settings */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Autopilot Settings
          </h3>
          <div className="grid grid-cols-2 gap-6">
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
