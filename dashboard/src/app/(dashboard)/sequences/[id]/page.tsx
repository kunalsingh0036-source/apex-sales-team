"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";

interface StepData {
  step_number: number;
  type: string;
  delay_days: number;
  channel: string;
  exit_on_reply: boolean;
  subject_variants: string[];
  body_variants: string[];
}

const STEP_TYPES = [
  { value: "cold_intro", label: "Cold Intro" },
  { value: "follow_up_1", label: "Follow-up 1" },
  { value: "follow_up_2", label: "Follow-up 2" },
  { value: "follow_up_3", label: "Follow-up 3" },
  { value: "breakup", label: "Breakup" },
  { value: "festive_gifting", label: "Festive Gifting" },
  { value: "event_triggered", label: "Event Triggered" },
  { value: "value_add", label: "Value Add" },
  { value: "case_study", label: "Case Study" },
];

const CHANNELS = [
  { value: "email", label: "Email" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "instagram", label: "Instagram" },
];

const CHANNEL_COLORS: Record<string, string> = {
  email: "bg-blue-100 text-blue-800",
  linkedin: "bg-sky-100 text-sky-800",
  whatsapp: "bg-green-100 text-green-800",
  instagram: "bg-pink-100 text-pink-800",
};

export default function SequenceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sequenceId = params.id as string;

  const [sequence, setSequence] = useState<any>(null);
  const [steps, setSteps] = useState<StepData[]>([]);
  const [editingStep, setEditingStep] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.sequences.get(sequenceId);
        setSequence(data);
        setSteps(data.steps || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sequenceId]);

  function addStep() {
    const newStep: StepData = {
      step_number: steps.length + 1,
      type: "follow_up_1",
      delay_days: 3,
      channel: sequence?.channel || "email",
      exit_on_reply: true,
      subject_variants: [],
      body_variants: [],
    };
    setSteps([...steps, newStep]);
    setEditingStep(steps.length);
    setDirty(true);
  }

  function removeStep(idx: number) {
    const newSteps = steps.filter((_, i) => i !== idx).map((s, i) => ({
      ...s,
      step_number: i + 1,
    }));
    setSteps(newSteps);
    setEditingStep(null);
    setDirty(true);
  }

  function updateStep(idx: number, updates: Partial<StepData>) {
    const newSteps = [...steps];
    newSteps[idx] = { ...newSteps[idx], ...updates };
    setSteps(newSteps);
    setDirty(true);
  }

  function moveStep(idx: number, direction: "up" | "down") {
    if (direction === "up" && idx === 0) return;
    if (direction === "down" && idx === steps.length - 1) return;
    const newSteps = [...steps];
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    [newSteps[idx], newSteps[swapIdx]] = [newSteps[swapIdx], newSteps[idx]];
    newSteps.forEach((s, i) => (s.step_number = i + 1));
    setSteps(newSteps);
    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await api.sequences.update(sequenceId, { steps });
      setDirty(false);
      alert("Sequence saved!");
    } catch (err: any) {
      alert("Failed: " + err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div><Header title="Loading..." /></div>;
  if (!sequence) return <div><Header title="Sequence Not Found" /></div>;

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => router.back()} className="text-crimson hover:text-crimson-dark text-sm">
          &larr; Back
        </button>
        <h2 className="font-display text-3xl font-bold text-crimson-dark">
          {sequence.name}
        </h2>
        <Badge variant={sequence.is_active ? "success" : "default"}>
          {sequence.is_active ? "Active" : "Inactive"}
        </Badge>
        <Badge variant="crimson">{sequence.channel}</Badge>
      </div>

      {sequence.description && (
        <p className="text-sm text-mid-warm mb-6">{sequence.description}</p>
      )}

      {/* Visual pipeline */}
      <div className="bg-white rounded-xl p-6 border border-rich-creme mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase">
            Sequence Steps ({steps.length})
          </h3>
          <div className="flex gap-2">
            {dirty && (
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save Changes"}
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={addStep}>
              + Add Step
            </Button>
          </div>
        </div>

        {/* Step flow visualization */}
        <div className="flex items-center gap-2 mb-6 flex-wrap">
          {steps.map((step, i) => (
            <div key={i} className="flex items-center gap-2">
              <button
                onClick={() => setEditingStep(editingStep === i ? null : i)}
                className={`px-3 py-2 rounded text-xs transition-all ${
                  editingStep === i
                    ? "ring-2 ring-crimson bg-crimson/10"
                    : "bg-creme hover:bg-rich-creme"
                }`}
              >
                <div className="font-bold text-warm-charcoal">
                  {STEP_TYPES.find((t) => t.value === step.type)?.label || step.type}
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className={`px-1 rounded text-[10px] ${CHANNEL_COLORS[step.channel] || "bg-gray-100 text-gray-700"}`}>
                    {step.channel}
                  </span>
                  {step.delay_days > 0 && (
                    <span className="text-mid-warm">+{step.delay_days}d</span>
                  )}
                </div>
              </button>
              {i < steps.length - 1 && (
                <span className="text-rich-creme text-lg">→</span>
              )}
            </div>
          ))}
        </div>

        {/* Step editor */}
        {editingStep !== null && steps[editingStep] && (
          <div className="border border-rich-creme rounded-lg p-6 bg-creme/30">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-display font-bold text-crimson-dark">
                Step {editingStep + 1}
              </h4>
              <div className="flex gap-2">
                <button
                  onClick={() => moveStep(editingStep, "up")}
                  disabled={editingStep === 0}
                  className="text-xs px-2 py-1 border border-rich-creme rounded hover:border-crimson disabled:opacity-30"
                >
                  Move Up
                </button>
                <button
                  onClick={() => moveStep(editingStep, "down")}
                  disabled={editingStep === steps.length - 1}
                  className="text-xs px-2 py-1 border border-rich-creme rounded hover:border-crimson disabled:opacity-30"
                >
                  Move Down
                </button>
                <button
                  onClick={() => removeStep(editingStep)}
                  className="text-xs px-2 py-1 border border-red-300 rounded text-red-600 hover:bg-red-50"
                >
                  Remove
                </button>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Type</label>
                <select
                  value={steps[editingStep].type}
                  onChange={(e) => updateStep(editingStep, { type: e.target.value })}
                  className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                >
                  {STEP_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Channel</label>
                <select
                  value={steps[editingStep].channel}
                  onChange={(e) => updateStep(editingStep, { channel: e.target.value })}
                  className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                >
                  {CHANNELS.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Delay (days)</label>
                <input
                  type="number"
                  min={0}
                  value={steps[editingStep].delay_days}
                  onChange={(e) => updateStep(editingStep, { delay_days: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
                />
              </div>
            </div>

            <div className="flex items-center gap-3 mb-4">
              <label className="flex items-center gap-2 text-sm text-warm-charcoal cursor-pointer">
                <input
                  type="checkbox"
                  checked={steps[editingStep].exit_on_reply}
                  onChange={(e) => updateStep(editingStep, { exit_on_reply: e.target.checked })}
                />
                Exit sequence on reply
              </label>
            </div>

            {/* A/B Variant editors */}
            <div className="space-y-3">
              <div>
                <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">
                  Subject Variants (A/B)
                </label>
                <div className="space-y-2">
                  {(steps[editingStep].subject_variants || []).map((sv, vi) => (
                    <div key={vi} className="flex gap-2">
                      <span className="text-xs font-bold text-crimson self-center w-4">
                        {vi === 0 ? "A" : "B"}
                      </span>
                      <input
                        value={sv}
                        onChange={(e) => {
                          const variants = [...(steps[editingStep].subject_variants || [])];
                          variants[vi] = e.target.value;
                          updateStep(editingStep, { subject_variants: variants });
                        }}
                        placeholder={`Subject variant ${vi === 0 ? "A" : "B"}`}
                        className="flex-1 px-3 py-1.5 border border-rich-creme rounded text-sm"
                      />
                      <button
                        onClick={() => {
                          const variants = (steps[editingStep].subject_variants || []).filter((_, i) => i !== vi);
                          updateStep(editingStep, { subject_variants: variants });
                        }}
                        className="text-xs text-red-500 hover:text-red-700"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                  {(steps[editingStep].subject_variants || []).length < 2 && (
                    <button
                      onClick={() => {
                        const variants = [...(steps[editingStep].subject_variants || []), ""];
                        updateStep(editingStep, { subject_variants: variants });
                      }}
                      className="text-xs text-crimson hover:text-crimson-dark"
                    >
                      + Add subject variant
                    </button>
                  )}
                </div>
              </div>

              <div>
                <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">
                  Body Variants (A/B)
                </label>
                <div className="space-y-2">
                  {(steps[editingStep].body_variants || []).map((bv, vi) => (
                    <div key={vi} className="flex gap-2">
                      <span className="text-xs font-bold text-crimson self-start mt-2 w-4">
                        {vi === 0 ? "A" : "B"}
                      </span>
                      <textarea
                        value={bv}
                        onChange={(e) => {
                          const variants = [...(steps[editingStep].body_variants || [])];
                          variants[vi] = e.target.value;
                          updateStep(editingStep, { body_variants: variants });
                        }}
                        placeholder={`Body variant ${vi === 0 ? "A" : "B"}. Use {{first_name}}, {{company_name}}, etc.`}
                        className="flex-1 px-3 py-1.5 border border-rich-creme rounded text-sm h-20 resize-y"
                      />
                      <button
                        onClick={() => {
                          const variants = (steps[editingStep].body_variants || []).filter((_, i) => i !== vi);
                          updateStep(editingStep, { body_variants: variants });
                        }}
                        className="text-xs text-red-500 hover:text-red-700 self-start mt-2"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                  {(steps[editingStep].body_variants || []).length < 2 && (
                    <button
                      onClick={() => {
                        const variants = [...(steps[editingStep].body_variants || []), ""];
                        updateStep(editingStep, { body_variants: variants });
                      }}
                      className="text-xs text-crimson hover:text-crimson-dark"
                    >
                      + Add body variant
                    </button>
                  )}
                </div>
              </div>
            </div>

            <p className="text-xs text-mid-warm mt-3">
              Leave variants empty to let AI generate personalized messages automatically.
              Add 2 variants for A/B testing.
            </p>
          </div>
        )}
      </div>

      {/* Sequence info */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-7 border border-rich-creme">
          <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Details</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-mid-warm">Primary Channel</span>
              <span className="font-bold text-warm-charcoal">{sequence.channel}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-mid-warm">Target Industry</span>
              <span className="font-bold text-warm-charcoal">{sequence.target_industry || "All"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-mid-warm">Created</span>
              <span className="font-bold text-warm-charcoal">
                {new Date(sequence.created_at).toLocaleDateString("en-IN")}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-mid-warm">Total Duration</span>
              <span className="font-bold text-warm-charcoal">
                {steps.reduce((sum, s) => sum + s.delay_days, 0)} days
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-7 border border-rich-creme">
          <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Channels Used</h3>
          <div className="flex flex-wrap gap-2">
            {[...new Set(steps.map((s) => s.channel))].map((ch) => (
              <div
                key={ch}
                className={`px-3 py-1.5 rounded text-xs font-bold ${CHANNEL_COLORS[ch] || "bg-gray-100 text-gray-700"}`}
              >
                {ch} ({steps.filter((s) => s.channel === ch).length} steps)
              </div>
            ))}
          </div>
          <p className="text-xs text-mid-warm mt-3">
            Multi-channel sequences respect cross-channel cooldowns (48hr min gap).
          </p>
        </div>
      </div>
    </div>
  );
}
