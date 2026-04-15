"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";

interface CampaignItem {
  id: string;
  name: string;
  status: string;
  total_leads: number;
  sequence: { id: string; name: string; channel: string } | null;
  started_at: string | null;
  created_at: string;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<CampaignItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const [generating, setGenerating] = useState(false);

  async function fetchData() {
    setLoading(true);
    try {
      const campaignData = await api.campaigns.list();
      setCampaigns(campaignData.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  async function handleCreateCampaigns() {
    setGenerating(true);
    try {
      const result = await api.autopilot.trigger('campaigns');
      toast("Campaigns are being created. Refresh in a moment.", "success");
      setTimeout(() => fetchData(), 3000);
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setGenerating(false);
    }
  }

  async function handleStatusChange(id: string, newStatus: string) {
    try {
      await api.campaigns.updateStatus(id, newStatus);
      fetchData();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleDeleteCampaign(id: string, name: string) {
    if (!confirm(`Delete campaign "${name}"? This will remove all enrollments and cannot be undone.`)) return;
    try {
      await api.campaigns.delete(id);
      fetchData();
    } catch (err: any) {
      toast(err.message, "error");
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
        <div className="flex flex-wrap gap-2 md:gap-3">
          <Button variant="outline" size="sm" onClick={handleCreateCampaigns} disabled={generating}>
            {generating ? "Running..." : "Create Campaigns"}
          </Button>
        </div>
      </div>

      {!loading && campaigns.length === 0 && (
        <div className="bg-white rounded-xl p-12 text-center border border-rich-creme">
          <p className="font-display text-xl text-crimson-dark mb-2">No campaigns yet</p>
          <p className="text-mid-warm text-sm">
            Click "Create Campaigns" to auto-generate campaigns from your leads.
          </p>
        </div>
      )}

      {!loading && campaigns.length > 0 && (
        <div className="space-y-4">
          {campaigns.map((c) => (
            <div
              key={c.id}
              className="bg-white rounded-xl p-7 border border-rich-creme"
            >
              <div className="flex items-start justify-between">
                <div>
                  <Link
                    href={`/campaigns/${c.id}`}
                    className="font-display text-xl font-bold text-crimson-dark hover:text-crimson"
                  >
                    {c.name}
                  </Link>
                  <div className="flex items-center gap-4 mt-3 text-sm text-mid-warm">
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
                  {c.status === "completed" && (
                    <Button
                      size="sm"
                      onClick={() => handleStatusChange(c.id, "active")}
                    >
                      Reactivate
                    </Button>
                  )}
                  {(c.status === "active" || c.status === "paused") && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleStatusChange(c.id, "completed")}
                    >
                      Complete
                    </Button>
                  )}
                  {c.status !== "active" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDeleteCampaign(c.id, c.name)}
                    >
                      Delete
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
