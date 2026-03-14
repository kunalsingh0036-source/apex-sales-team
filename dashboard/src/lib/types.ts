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

// --- CRM Types ---

export interface Client {
  id: string;
  company_id: string;
  lead_id: string | null;
  primary_contact_name: string;
  primary_contact_email: string | null;
  primary_contact_phone: string | null;
  primary_contact_title: string | null;
  ama_tier: AMATier | null;
  ama_commitment: number | null;
  ama_start_date: string | null;
  ama_end_date: string | null;
  status: string;
  billing_address: string | null;
  shipping_address: string | null;
  gst_number: string | null;
  payment_terms: string | null;
  notes: string;
  tags: string[];
  extra_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type AMATier = "bronze" | "silver" | "gold" | "institutional";

export const AMA_TIER_LABELS: Record<AMATier, string> = {
  bronze: "Bronze",
  silver: "Silver",
  gold: "Gold",
  institutional: "Institutional",
};

export const AMA_TIER_COLORS: Record<AMATier, string> = {
  bronze: "bg-amber-100 text-amber-800",
  silver: "bg-gray-200 text-gray-700",
  gold: "bg-yellow-100 text-yellow-800",
  institutional: "bg-purple-100 text-purple-800",
};

export interface ClientContact {
  id: string;
  client_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  title: string | null;
  department: string | null;
  is_primary: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface BrandAsset {
  id: string;
  client_id: string;
  asset_type: string;
  name: string;
  value: string | null;
  file_url: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Interaction {
  id: string;
  client_id: string;
  type: string;
  subject: string;
  description: string;
  interaction_date: string;
  performed_by: string | null;
  follow_up_date: string | null;
  extra_data: Record<string, unknown>;
  created_at: string;
}

export interface SampleKit {
  id: string;
  client_id: string | null;
  lead_id: string | null;
  recipient_name: string;
  recipient_company: string | null;
  kit_name: string;
  contents: unknown[];
  status: string;
  sent_date: string | null;
  delivered_date: string | null;
  follow_up_date: string | null;
  tracking_number: string | null;
  feedback: string;
  conversion_status: string | null;
  extra_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProductCategory {
  id: string;
  name: string;
  parent_id: string | null;
  description: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  name: string;
  sku: string | null;
  category_id: string;
  description: string;
  gsm_range: string | null;
  available_sizes: string[];
  available_colors: string[];
  available_customizations: string[];
  base_price: number | null;
  pricing_tiers: Record<string, unknown>;
  min_order_qty: number;
  lead_time_days: number | null;
  is_active: boolean;
  image_urls: string[];
  extra_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type OrderStage = "brief" | "design" | "tech_spec" | "sampling" | "production" | "qc" | "delivery";

export const ORDER_STAGE_LABELS: Record<OrderStage, string> = {
  brief: "Brief",
  design: "Design",
  tech_spec: "Tech Spec",
  sampling: "Sampling",
  production: "Production",
  qc: "QC",
  delivery: "Delivery",
};

export const ORDER_STAGE_COLORS: Record<OrderStage, string> = {
  brief: "bg-gray-200 text-gray-800",
  design: "bg-blue-100 text-blue-800",
  tech_spec: "bg-indigo-100 text-indigo-800",
  sampling: "bg-amber-100 text-amber-800",
  production: "bg-orange-100 text-orange-800",
  qc: "bg-purple-100 text-purple-800",
  delivery: "bg-green-100 text-green-800",
};

export interface Order {
  id: string;
  client_id: string;
  quote_id: string | null;
  order_number: string;
  stage: OrderStage;
  subtotal: number;
  gst_rate: number;
  gst_amount: number;
  discount_percent: number;
  discount_amount: number;
  total_amount: number;
  currency: string;
  expected_delivery_date: string | null;
  actual_delivery_date: string | null;
  brief_received_date: string | null;
  shipping_address: string | null;
  billing_address: string | null;
  notes: string;
  priority: string;
  assigned_to: string | null;
  extra_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  line_items: OrderItem[];
}

export interface OrderItem {
  id: string;
  order_id: string;
  product_id: string | null;
  product_name: string;
  description: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  size_breakdown: Record<string, unknown>;
  color: string | null;
  gsm: number | null;
  customization_type: string | null;
  customization_details: string;
  extra_data: Record<string, unknown>;
}

export interface OrderStageLog {
  id: string;
  order_id: string;
  from_stage: string | null;
  to_stage: string;
  notes: string;
  changed_by: string | null;
  created_at: string;
}

export interface Quote {
  id: string;
  client_id: string;
  quote_number: string;
  status: string;
  subtotal: number;
  gst_rate: number;
  gst_amount: number;
  discount_percent: number;
  discount_amount: number;
  total_amount: number;
  currency: string;
  valid_from: string;
  valid_until: string;
  payment_terms: string | null;
  delivery_terms: string | null;
  notes: string;
  terms_and_conditions: string;
  converted_to_order_id: string | null;
  sent_at: string | null;
  viewed_at: string | null;
  accepted_at: string | null;
  created_by: string | null;
  extra_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  line_items: QuoteItem[];
}

export interface QuoteItem {
  id: string;
  quote_id: string;
  product_id: string | null;
  product_name: string;
  description: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  size_breakdown: Record<string, unknown>;
  color: string | null;
  gsm: number | null;
  customization_type: string | null;
  customization_details: string;
}

export const QUOTE_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-200 text-gray-800",
  sent: "bg-blue-100 text-blue-800",
  viewed: "bg-amber-100 text-amber-800",
  accepted: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  expired: "bg-gray-300 text-gray-600",
  converted: "bg-purple-100 text-purple-800",
};
