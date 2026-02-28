"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";

interface CampaignItem {
  id: string;
  name: string;
  status: string;
  total_leads: number;
  sequence: { id: string; name: string; channel: string } | null;
  started_at: string | null;
  created_at: string;
}

interface SequenceOption {
  id: string;
  name: string;
  channel: string;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<CampaignItem[]>([]);
  const [sequences, setSequences] = useState<SequenceOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", sequence_id: "" });

  async function fetchData() {
    setLoading(true);
    try {
      const [campaignData, seqData] = await Promise.all([
        api.campaigns.list(),
        api.sequences.list(),
      ]);
      setCampaigns(campaignData.items);
      setSequences(seqData.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.campaigns.create({
        name: form.name,
        sequence_id: form.sequence_id,
      });
      setShowCreate(false);
      setForm({ name: "", sequence_id: "" });
      fetchData();
    } catch (err: any) {
      alert("Failed: " + err.message);
    }
  }

  async function handleStatusChange(id: string, newStatus: string) {
    try {
      await api.campaigns.updateStatus(id, newStatus);
      fetchData();
    } catch (err: any) {
      alert("Failed: " + err.message);
    }
  }

  const statusVariant: Record<string, "default" | "success" | "warning" | "crimson" | "info"> = {
    draft: "default",
    active: "success",
    paused: "warning",
    completed: "info",
  };

  return (
    <div>
      <Header title="Campaigns" />

      <div className="flex justify-between items-center mb-6">
        <p className="text-sm text-mid-warm">
          {loading ? "Loading..." : `${campaigns.length} campaigns`}
        </p>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          + New Campaign
        </Button>
      </div>

      {showCreate && (
        <div className="mb-6 bg-white rounded-lg p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Create Campaign
          </h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <input
              required
              placeholder="Campaign name *"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <select
              required
              value={form.sequence_id}
              onChange={(e) => setForm({ ...form, sequence_id: e.target.value })}
              className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
            >
              <option value="">Select a sequence *</option>
              {sequences.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.channel})
                </option>
              ))}
            </select>
            {sequences.length === 0 && (
              <p className="text-xs text-crimson">
                No sequences available. <Link href="/sequences" className="underline">Create one first</Link>.
              </p>
            )}
            <div className="flex gap-3">
              <Button type="submit" size="sm" disabled={!form.sequence_id}>
                Create Campaign
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {!loading && campaigns.length === 0 && (
        <div className="bg-white rounded-lg p-12 text-center border border-rich-creme">
          <p className="font-display text-xl text-crimson-dark mb-2">No campaigns yet</p>
          <p className="text-mid-warm text-sm">
            Create a sequence first, then create a campaign to enroll leads.
          </p>
        </div>
      )}

      {!loading && campaigns.length > 0 && (
        <div className="space-y-4">
          {campaigns.map((c) => (
            <div
              key={c.id}
              className="bg-white rounded-lg p-6 border border-rich-creme"
            >
              <div className="flex items-start justify-between">
                <div>
                  <Link
                    href={`/campaigns/${c.id}`}
                    className="font-display text-lg font-bold text-crimson-dark hover:text-crimson"
                  >
                    {c.name}
                  </Link>
                  <div className="flex items-center gap-3 mt-2 text-sm text-mid-warm">
                    <span>{c.total_leads} leads enrolled</span>
                    {c.sequence && <span>Sequence: {c.sequence.name}</span>}
                    {c.started_at && (
                      <span>
                        Started {new Date(c.started_at).toLocaleDateString("en-IN")}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={statusVariant[c.status] || "default"}>
                    {c.status}
                  </Badge>
                  {c.status === "draft" && (
                    <Button
                      size="sm"
                      onClick={() => handleStatusChange(c.id, "active")}
                    >
                      Start
                    </Button>
                  )}
                  {c.status === "active" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleStatusChange(c.id, "paused")}
                    >
                      Pause
                    </Button>
                  )}
                  {c.status === "paused" && (
                    <Button
                      size="sm"
                      onClick={() => handleStatusChange(c.id, "active")}
                    >
                      Resume
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
