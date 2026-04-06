const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Dashboard
  dashboard: {
    stats: () => request<any>("/dashboard/stats"),
  },

  // Leads
  leads: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/leads${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/leads/${id}`),
    create: (data: any) =>
      request<any>("/leads", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/leads/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<any>(`/leads/${id}`, { method: "DELETE" }),
    updateStage: (id: string, stage: string) =>
      request<any>(`/leads/${id}/stage`, {
        method: "PUT",
        body: JSON.stringify({ stage }),
      }),
    timeline: (id: string) => request<any[]>(`/leads/${id}/timeline`),
    bulkImport: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/leads/bulk-import`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `API error: ${res.status}`);
      }
      return res.json();
    },
  },

  // Companies
  companies: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/companies${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/companies/${id}`),
    create: (data: any) =>
      request<any>("/companies", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/companies/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<any>(`/companies/${id}`, { method: "DELETE" }),
  },

  // Sequences
  sequences: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/sequences${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/sequences/${id}`),
    create: (data: any) =>
      request<any>("/sequences", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/sequences/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<any>(`/sequences/${id}`, { method: "DELETE" }),
    duplicate: (id: string) =>
      request<any>(`/sequences/${id}/duplicate`, { method: "POST" }),
  },

  // Campaigns
  campaigns: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/campaigns${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/campaigns/${id}`),
    create: (data: any) =>
      request<any>("/campaigns", { method: "POST", body: JSON.stringify(data) }),
    updateStatus: (id: string, status: string) =>
      request<any>(`/campaigns/${id}/status`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      }),
    delete: (id: string) =>
      request<any>(`/campaigns/${id}`, { method: "DELETE" }),
    enroll: (id: string, leadIds: string[]) =>
      request<any>(`/campaigns/${id}/enroll`, {
        method: "POST",
        body: JSON.stringify({ lead_ids: leadIds }),
      }),
    enrollments: (id: string, params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/campaigns/${id}/enrollments${qs ? `?${qs}` : ""}`);
    },
  },

  // Templates
  templates: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/templates${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/templates/${id}`),
    create: (data: any) =>
      request<any>("/templates", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/templates/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<any>(`/templates/${id}`, { method: "DELETE" }),
    generate: (params: Record<string, string>) => {
      const search = new URLSearchParams(params);
      return request<any>(`/templates/generate?${search.toString()}`, {
        method: "POST",
      });
    },
  },

  // Messages
  messages: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/messages${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/messages/${id}`),
    send: (data: any) =>
      request<any>("/messages/send", { method: "POST", body: JSON.stringify(data) }),
    generate: (data: any) =>
      request<any>("/messages/generate", { method: "POST", body: JSON.stringify(data) }),
    pendingReplies: () => request<any[]>("/messages/pending-replies"),
    suggestReply: (id: string) => request<any>(`/messages/${id}/suggest-reply`),
    classify: (id: string, classification: string) =>
      request<any>(`/messages/${id}/classify?classification=${classification}`, {
        method: "POST",
      }),
  },

  // Discovery & Enrichment
  discovery: {
    searchPeople: (data: any) =>
      request<any>("/discovery/search/people", { method: "POST", body: JSON.stringify(data) }),
    searchCompanies: (data: any) =>
      request<any>("/discovery/search/companies", { method: "POST", body: JSON.stringify(data) }),
    importFromApollo: (data: any) =>
      request<any>("/discovery/import", { method: "POST", body: JSON.stringify(data) }),
    verifyEmail: (email: string) =>
      request<any>(`/discovery/verify-email?email=${encodeURIComponent(email)}`),
    findEmail: (domain: string, firstName: string, lastName: string) =>
      request<any>(`/discovery/find-email?domain=${encodeURIComponent(domain)}&first_name=${encodeURIComponent(firstName)}&last_name=${encodeURIComponent(lastName)}`),
    enrichLead: (id: string) =>
      request<any>(`/discovery/enrich/lead/${id}`, { method: "POST" }),
    enrichCompany: (id: string) =>
      request<any>(`/discovery/enrich/company/${id}`, { method: "POST" }),
    batchScore: () =>
      request<any>("/discovery/score/batch", { method: "POST" }),
  },

  // Clients
  clients: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/clients${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/clients/${id}`),
    create: (data: any) =>
      request<any>("/clients", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/clients/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    convertLead: (data: any) =>
      request<any>("/clients/convert-lead", { method: "POST", body: JSON.stringify(data) }),
    revenue: (id: string) => request<any>(`/clients/${id}/revenue`),
    contacts: (id: string) => request<any>(`/clients/${id}/contacts`),
    createContact: (clientId: string, data: any) =>
      request<any>(`/clients/${clientId}/contacts`, { method: "POST", body: JSON.stringify(data) }),
    brandAssets: (id: string) => request<any>(`/clients/${id}/brand-assets`),
    createBrandAsset: (clientId: string, data: any) =>
      request<any>(`/clients/${clientId}/brand-assets`, { method: "POST", body: JSON.stringify(data) }),
    interactions: (id: string) => request<any>(`/clients/${id}/interactions`),
    createInteraction: (clientId: string, data: any) =>
      request<any>(`/clients/${clientId}/interactions`, { method: "POST", body: JSON.stringify(data) }),
    sampleKits: (id: string) => request<any>(`/clients/${id}/sample-kits`),
  },

  // Orders
  orders: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/orders${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/orders/${id}`),
    create: (data: any) =>
      request<any>("/orders", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/orders/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    advanceStage: (id: string, data: any) =>
      request<any>(`/orders/${id}/advance-stage`, { method: "POST", body: JSON.stringify(data) }),
    stageHistory: (id: string) => request<any>(`/orders/${id}/stage-history`),
    pipeline: () => request<any>("/orders/pipeline"),
  },

  // Products
  products: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/products${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/products/${id}`),
    create: (data: any) =>
      request<any>("/products", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<any>(`/products/${id}`, { method: "DELETE" }),
    categories: () => request<any>("/products/categories"),
    createCategory: (data: any) =>
      request<any>("/products/categories", { method: "POST", body: JSON.stringify(data) }),
  },

  // Quotes
  quotes: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
        });
      }
      const qs = search.toString();
      return request<any>(`/quotes${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<any>(`/quotes/${id}`),
    create: (data: any) =>
      request<any>("/quotes", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/quotes/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    updateStatus: (id: string, status: string) =>
      request<any>(`/quotes/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
    convertToOrder: (id: string, data: any) =>
      request<any>(`/quotes/${id}/convert-to-order`, { method: "POST", body: JSON.stringify(data) }),
  },

  // Revenue
  revenue: {
    dashboard: () => request<any>("/revenue/dashboard"),
    byClient: (limit?: number) =>
      request<any>(`/revenue/by-client${limit ? `?limit=${limit}` : ""}`),
    monthlyTrends: (months?: number) =>
      request<any>(`/revenue/monthly-trends${months ? `?months=${months}` : ""}`),
    pipelineValue: () => request<any>("/revenue/pipeline-value"),
    amaOverview: () => request<any>("/revenue/ama-overview"),
  },

  // Autopilot
  autopilot: {
    status: () => request<any>("/automation/status"),
    toggle: (enabled: boolean) =>
      request<any>("/automation/toggle", { method: "PUT", body: JSON.stringify({ enabled }) }),
    getIcp: () => request<any>("/automation/icp"),
    updateIcp: (data: any) =>
      request<any>("/automation/icp", { method: "PUT", body: JSON.stringify(data) }),
    history: (limit?: number) =>
      request<any>(`/automation/history${limit ? `?limit=${limit}` : ""}`),
    trigger: (stage: string) =>
      request<any>(`/automation/trigger/${stage}`, { method: "POST" }),
    getSettings: () => request<any>("/automation/settings"),
    updateSettings: (data: any) =>
      request<any>("/automation/settings", { method: "PUT", body: JSON.stringify(data) }),
  },

  // Analytics
  analytics: {
    overview: (days?: number) =>
      request<any>(`/analytics/overview${days ? `?days=${days}` : ""}`),
    dailyTrends: (days?: number, channel?: string) => {
      const params = new URLSearchParams();
      if (days) params.set("days", String(days));
      if (channel) params.set("channel", channel);
      const qs = params.toString();
      return request<any[]>(`/analytics/daily-trends${qs ? `?${qs}` : ""}`);
    },
    channels: (days?: number) =>
      request<any[]>(`/analytics/channels${days ? `?days=${days}` : ""}`),
    funnel: () => request<any[]>("/analytics/funnel"),
    campaigns: () => request<any[]>("/analytics/campaigns"),
    abTests: (campaignId?: string) =>
      request<any[]>(`/analytics/ab-tests${campaignId ? `?campaign_id=${campaignId}` : ""}`),
    leadScores: () => request<any[]>("/analytics/lead-scores"),
    aiInsights: () => request<any>("/analytics/ai-insights"),
  },
};
