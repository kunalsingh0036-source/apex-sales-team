"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";

interface SequenceItem {
  id: string;
  name: string;
  description: string | null;
  channel: string;
  target_industry: string | null;
  is_active: boolean;
  steps: any[];
  created_at: string;
}

export default function SequencesPage() {
  const [sequences, setSequences] = useState<SequenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    channel: "email",
    target_industry: "",
  });

  async function fetchSequences() {
    setLoading(true);
    try {
      const data = await api.sequences.list();
      setSequences(data.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchSequences();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.sequences.create({
        ...form,
        target_industry: form.target_industry || null,
        steps: [
          {
            step_number: 1,
            type: "cold_intro",
            delay_days: 0,
            channel: form.channel,
            exit_on_reply: true,
            subject_variants: [],
            body_variants: [],
          },
          {
            step_number: 2,
            type: "follow_up_1",
            delay_days: 3,
            channel: form.channel,
            exit_on_reply: true,
            subject_variants: [],
            body_variants: [],
          },
          {
            step_number: 3,
            type: "follow_up_2",
            delay_days: 5,
            channel: form.channel,
            exit_on_reply: true,
            subject_variants: [],
            body_variants: [],
          },
          {
            step_number: 4,
            type: "breakup",
            delay_days: 7,
            channel: form.channel,
            exit_on_reply: true,
            subject_variants: [],
            body_variants: [],
          },
        ],
      });
      setShowCreate(false);
      setForm({ name: "", description: "", channel: "email", target_industry: "" });
      fetchSequences();
    } catch (err: any) {
      alert("Failed: " + err.message);
    }
  }

  async function handleDuplicate(id: string) {
    try {
      await api.sequences.duplicate(id);
      fetchSequences();
    } catch (err: any) {
      alert("Failed: " + err.message);
    }
  }

  async function handleDeleteSequence(id: string, name: string) {
    if (!confirm(`Delete sequence "${name}"? This cannot be undone.`)) return;
    try {
      await api.sequences.delete(id);
      fetchSequences();
    } catch (err: any) {
      alert("Failed: " + err.message);
    }
  }

  async function handleToggleActive(seq: SequenceItem) {
    try {
      await api.sequences.update(seq.id, { is_active: !seq.is_active });
      fetchSequences();
    } catch (err: any) {
      alert("Failed: " + err.message);
    }
  }

  const stepTypeLabels: Record<string, string> = {
    cold_intro: "Cold Intro",
    follow_up_1: "Follow-up 1",
    follow_up_2: "Follow-up 2",
    breakup: "Breakup",
    festive_gifting: "Festive Gifting",
    event_triggered: "Event Triggered",
  };

  return (
    <div>
      <Header title="Sequences" />

      <div className="flex justify-between items-center mb-6">
        <p className="text-sm text-mid-warm">
          {loading ? "Loading..." : `${sequences.length} sequences`}
        </p>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          + New Sequence
        </Button>
      </div>

      {showCreate && (
        <div className="mb-6 bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Create Sequence
          </h3>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <input
              required
              placeholder="Sequence name *"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm col-span-2"
            />
            <input
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm col-span-2"
            />
            <select
              value={form.channel}
              onChange={(e) => setForm({ ...form, channel: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            >
              <option value="email">Email</option>
              <option value="linkedin">LinkedIn</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="instagram">Instagram</option>
            </select>
            <select
              value={form.target_industry}
              onChange={(e) => setForm({ ...form, target_industry: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            >
              <option value="">All Industries</option>
              <option value="Technology & SaaS">Technology & SaaS</option>
              <option value="Banking & Financial Services">Banking & Finance</option>
              <option value="Defence & Government">Defence & Government</option>
              <option value="Hospitality & Luxury Hotels">Hospitality</option>
              <option value="Healthcare & Pharmaceuticals">Healthcare</option>
              <option value="Real Estate & Infrastructure">Real Estate</option>
              <option value="Educational Institutions">Education</option>
              <option value="Events & Activations">Events</option>
            </select>
            <div className="col-span-2 flex gap-3">
              <Button type="submit" size="sm">Create (4-step default)</Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
            </div>
            <p className="col-span-2 text-xs text-mid-warm">
              Creates a 4-step sequence: Cold Intro → Follow-up 1 (Day 3) → Follow-up 2 (Day 5) → Breakup (Day 7).
              AI generates personalized messages for each step.
            </p>
          </form>
        </div>
      )}

      {!loading && sequences.length === 0 && (
        <div className="bg-white rounded-xl p-12 text-center border border-rich-creme">
          <p className="font-display text-xl text-crimson-dark mb-2">No sequences yet</p>
          <p className="text-mid-warm text-sm">
            Create your first outreach sequence to start automating sales.
          </p>
        </div>
      )}

      {!loading && sequences.length > 0 && (
        <div className="space-y-4">
          {sequences.map((seq) => (
            <div
              key={seq.id}
              className="bg-white rounded-xl p-7 border border-rich-creme"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <Link
                    href={`/sequences/${seq.id}`}
                    className="font-display text-lg font-bold text-crimson-dark hover:text-crimson"
                  >
                    {seq.name}
                  </Link>
                  {seq.description && (
                    <p className="text-sm text-mid-warm mt-1">{seq.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={seq.is_active ? "success" : "default"}>
                    {seq.is_active ? "Active" : "Inactive"}
                  </Badge>
                  <Badge variant="crimson">{seq.channel}</Badge>
                </div>
              </div>

              {/* Steps visualization */}
              <div className="flex items-center gap-2 mt-4">
                {seq.steps.map((step: any, i: number) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="px-3.5 py-2 bg-creme rounded text-xs text-warm-charcoal">
                      <span className="font-bold">
                        {stepTypeLabels[step.type] || step.type}
                      </span>
                      {step.delay_days > 0 && (
                        <span className="text-mid-warm ml-1">+{step.delay_days}d</span>
                      )}
                    </div>
                    {i < seq.steps.length - 1 && (
                      <span className="text-rich-creme">→</span>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-2 mt-4">
                <Link href={`/sequences/${seq.id}`}>
                  <Button variant="outline" size="sm">Edit Steps</Button>
                </Link>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDuplicate(seq.id)}
                >
                  Duplicate
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleToggleActive(seq)}
                >
                  {seq.is_active ? "Deactivate" : "Activate"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDeleteSequence(seq.id, seq.name)}
                >
                  Delete
                </Button>
                {seq.target_industry && (
                  <Badge variant="default">{seq.target_industry}</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
