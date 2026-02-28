export interface Company {
  id: string;
  name: string;
  domain: string | null;
  industry: string;
  sub_industry: string | null;
  employee_count: string | null;
  headquarters: string | null;
  linkedin_url: string | null;
  website: string | null;
  annual_revenue: string | null;
  enrichment_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: string;
  company_id: string | null;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  email_verified: boolean;
  phone: string | null;
  whatsapp_number: string | null;
  linkedin_url: string | null;
  instagram_handle: string | null;
  job_title: string;
  department: string | null;
  seniority: string | null;
  city: string | null;
  state: string | null;
  country: string;
  source: string;
  lead_score: number;
  score_breakdown: Record<string, number>;
  stage: LeadStage;
  deal_value: number | null;
  tags: string[];
  notes: string;
  consent_status: string;
  do_not_contact: boolean;
  created_at: string;
  updated_at: string;
  company: Company | null;
}

export type LeadStage =
  | "prospect"
  | "contacted"
  | "engaged"
  | "qualified"
  | "proposal_sent"
  | "negotiation"
  | "won"
  | "lost"
  | "nurture";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface Activity {
  id: string;
  type: string;
  channel: string | null;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export const STAGE_LABELS: Record<LeadStage, string> = {
  prospect: "Prospect",
  contacted: "Contacted",
  engaged: "Engaged",
  qualified: "Qualified",
  proposal_sent: "Proposal Sent",
  negotiation: "Negotiation",
  won: "Won",
  lost: "Lost",
  nurture: "Nurture",
};

export const STAGE_COLORS: Record<LeadStage, string> = {
  prospect: "bg-gray-200 text-gray-800",
  contacted: "bg-blue-100 text-blue-800",
  engaged: "bg-amber-100 text-amber-800",
  qualified: "bg-purple-100 text-purple-800",
  proposal_sent: "bg-indigo-100 text-indigo-800",
  negotiation: "bg-orange-100 text-orange-800",
  won: "bg-green-100 text-green-800",
  lost: "bg-red-100 text-red-800",
  nurture: "bg-teal-100 text-teal-800",
};

export const INDUSTRIES = [
  "Banking & Financial Services",
  "Technology & SaaS",
  "Defence & Government",
  "Hospitality & Luxury Hotels",
  "Healthcare & Pharmaceuticals",
  "Real Estate & Infrastructure",
  "Retail & Consumer Brands",
  "Educational Institutions",
  "Events & Activations",
  "Other",
];

export const SENIORITY_LEVELS = [
  "entry",
  "manager",
  "director",
  "vp",
  "c_level",
  "founder",
];

export const DEPARTMENTS = [
  "Procurement",
  "HR",
  "Admin",
  "Marketing",
  "Brand",
  "Operations",
  "C-Suite",
  "Other",
];
