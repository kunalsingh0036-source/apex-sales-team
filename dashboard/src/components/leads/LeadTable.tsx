"use client";

import Link from "next/link";
import Badge from "@/components/ui/Badge";
import { Lead, STAGE_LABELS, LeadStage } from "@/lib/types";

function ScoreBadge({ score }: { score: number }) {
  let variant: "success" | "warning" | "danger" | "default" = "default";
  if (score >= 70) variant = "success";
  else if (score >= 40) variant = "warning";
  else if (score > 0) variant = "danger";

  return <Badge variant={variant}>{score}</Badge>;
}

function StageBadge({ stage }: { stage: LeadStage }) {
  const variantMap: Record<string, "success" | "warning" | "danger" | "info" | "crimson" | "default"> = {
    prospect: "default",
    contacted: "info",
    engaged: "warning",
    qualified: "crimson",
    proposal_sent: "info",
    negotiation: "warning",
    won: "success",
    lost: "danger",
    nurture: "default",
  };

  return (
    <Badge variant={variantMap[stage] || "default"}>
      {STAGE_LABELS[stage] || stage}
    </Badge>
  );
}

export default function LeadTable({ leads }: { leads: Lead[] }) {
  if (leads.length === 0) {
    return (
      <div className="bg-white rounded-lg p-12 text-center border border-rich-creme">
        <p className="font-display text-xl text-crimson-dark mb-2">No leads yet</p>
        <p className="text-mid-warm text-sm">
          Import a CSV or add leads manually to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-rich-creme overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-rich-creme bg-creme/50">
            <th className="text-left px-4 py-3 font-label text-xs tracking-[0.15em] text-mid-warm uppercase">
              Name
            </th>
            <th className="text-left px-4 py-3 font-label text-xs tracking-[0.15em] text-mid-warm uppercase">
              Company
            </th>
            <th className="text-left px-4 py-3 font-label text-xs tracking-[0.15em] text-mid-warm uppercase">
              Title
            </th>
            <th className="text-left px-4 py-3 font-label text-xs tracking-[0.15em] text-mid-warm uppercase">
              Stage
            </th>
            <th className="text-center px-4 py-3 font-label text-xs tracking-[0.15em] text-mid-warm uppercase">
              Score
            </th>
            <th className="text-left px-4 py-3 font-label text-xs tracking-[0.15em] text-mid-warm uppercase">
              Source
            </th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => (
            <tr
              key={lead.id}
              className="border-b border-rich-creme/50 hover:bg-creme/30 transition-colors"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/leads/${lead.id}`}
                  className="font-bold text-crimson-dark hover:text-crimson transition-colors"
                >
                  {lead.full_name}
                </Link>
                {lead.email && (
                  <p className="text-xs text-mid-warm mt-0.5">{lead.email}</p>
                )}
              </td>
              <td className="px-4 py-3 text-sm">
                {lead.company?.name || "—"}
                {lead.company?.industry && (
                  <p className="text-xs text-mid-warm mt-0.5">
                    {lead.company.industry}
                  </p>
                )}
              </td>
              <td className="px-4 py-3 text-sm text-warm-charcoal">
                {lead.job_title}
                {lead.department && (
                  <p className="text-xs text-mid-warm mt-0.5">{lead.department}</p>
                )}
              </td>
              <td className="px-4 py-3">
                <StageBadge stage={lead.stage} />
              </td>
              <td className="px-4 py-3 text-center">
                <ScoreBadge score={lead.lead_score} />
              </td>
              <td className="px-4 py-3">
                <span className="font-label text-xs tracking-wider text-mid-warm uppercase">
                  {lead.source}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
