"use client";

import { useEffect, useState, useRef } from "react";
import Header from "@/components/layout/Header";
import LeadTable from "@/components/leads/LeadTable";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";
import { Lead, PaginatedResponse, INDUSTRIES, SENIORITY_LEVELS } from "@/lib/types";

interface PersonResult {
  first_name: string;
  last_name: string;
  name: string;
  title: string;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  city: string;
  seniority: string;
  company: { name: string; domain: string; industry: string; employee_count: number | null };
}

const APEX_INDUSTRIES = [
  { value: "technology", label: "Technology & SaaS" },
  { value: "banking", label: "Banking & Finance" },
  { value: "defense", label: "Defence & Government" },
  { value: "hospitality", label: "Hospitality & Hotels" },
  { value: "healthcare", label: "Healthcare" },
  { value: "real estate", label: "Real Estate" },
  { value: "education", label: "Education" },
  { value: "events", label: "Events & Activations" },
];

const APEX_ROLES = [
  "CEO", "COO", "CFO", "CMO", "CHRO",
  "Head of Procurement", "Head of HR",
  "VP Operations", "VP Marketing",
  "Director of Administration",
  "Purchase Manager", "Brand Manager",
];

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [generating, setGenerating] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showDiscovery, setShowDiscovery] = useState(false);

  // Discovery state
  const [discoverySearching, setDiscoverySearching] = useState(false);
  const [discoveryResults, setDiscoveryResults] = useState<PersonResult[]>([]);
  const [discoveryTotal, setDiscoveryTotal] = useState(0);
  const [discoveryImporting, setDiscoveryImporting] = useState(false);
  const [discoveryForm, setDiscoveryForm] = useState({
    job_titles: [] as string[],
    industries: [] as string[],
    locations: ["India"],
    company_sizes: [] as string[],
    keywords: "",
  });
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", email: "", job_title: "", phone: "", department: "" });
  const [editSaving, setEditSaving] = useState(false);
  const [emailVerify, setEmailVerify] = useState({ email: "", result: null as any, loading: false });
  const [emailFind, setEmailFind] = useState({ domain: "", firstName: "", lastName: "", result: null as any, loading: false });
  const { toast } = useToast();
  const [newLead, setNewLead] = useState({
    first_name: "",
    last_name: "",
    email: "",
    job_title: "",
    phone: "",
    department: "",
    seniority: "",
  });

  async function fetchLeads() {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: 50 };
      if (search) params.search = search;
      if (stageFilter) params.stage = stageFilter;
      if (emailFilter) params.has_email = emailFilter;
      const data: PaginatedResponse<Lead> = await api.leads.list(params);
      setLeads(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      console.error("Failed to fetch leads:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLeads();
  }, [page, stageFilter, emailFilter]);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchLeads();
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const result = await api.leads.bulkImport(file);
      setImportResult(result);
      fetchLeads();
    } catch (err: any) {
      setImportResult({ success: false, error: err.message });
    }
  }

  async function handleDiscover() {
    setGenerating(true);
    try {
      const result = await api.autopilot.trigger('discover');
      toast("Discovering new leads. Refresh in a moment.", "success");
      setTimeout(() => fetchLeads(), 5000);
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setGenerating(false);
    }
  }

  async function handleAddLead(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.leads.create(newLead);
      setShowAddForm(false);
      setNewLead({
        first_name: "",
        last_name: "",
        email: "",
        job_title: "",
        phone: "",
        department: "",
        seniority: "",
      });
      fetchLeads();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  function openEditLead(lead: Lead) {
    setEditingLead(lead);
    setEditForm({
      first_name: lead.first_name,
      last_name: lead.last_name,
      email: lead.email || "",
      job_title: lead.job_title,
      phone: lead.phone || "",
      department: lead.department || "",
    });
  }

  async function handleEditLead(e: React.FormEvent) {
    e.preventDefault();
    if (!editingLead) return;
    setEditSaving(true);
    try {
      await api.leads.update(editingLead.id, editForm);
      toast("Lead updated.", "success");
      setEditingLead(null);
      fetchLeads();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDeleteLead(lead: Lead) {
    if (!confirm(`Delete lead "${lead.full_name}"? This cannot be undone.`)) return;
    try {
      await api.leads.delete(lead.id);
      toast("Lead deleted.", "success");
      fetchLeads();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleDiscoverySearch() {
    setDiscoverySearching(true);
    setDiscoveryResults([]);
    try {
      const data = await api.discovery.searchPeople({
        job_titles: discoveryForm.job_titles.length > 0 ? discoveryForm.job_titles : undefined,
        industries: discoveryForm.industries.length > 0 ? discoveryForm.industries : undefined,
        locations: discoveryForm.locations.length > 0 ? discoveryForm.locations : undefined,
        company_sizes: discoveryForm.company_sizes.length > 0 ? discoveryForm.company_sizes : undefined,
        keywords: discoveryForm.keywords ? discoveryForm.keywords.split(",").map((k: string) => k.trim()) : undefined,
      });
      setDiscoveryResults(data.people || []);
      setDiscoveryTotal(data.total || 0);
    } catch (err: any) { toast(err.message, "error"); }
    finally { setDiscoverySearching(false); }
  }

  async function handleDiscoveryImport() {
    setDiscoveryImporting(true);
    try {
      const data = await api.discovery.importFromApollo({
        job_titles: discoveryForm.job_titles.length > 0 ? discoveryForm.job_titles : undefined,
        industries: discoveryForm.industries.length > 0 ? discoveryForm.industries : undefined,
        locations: discoveryForm.locations,
        company_sizes: discoveryForm.company_sizes.length > 0 ? discoveryForm.company_sizes : undefined,
        keywords: discoveryForm.keywords ? discoveryForm.keywords.split(",").map((k: string) => k.trim()) : undefined,
        max_results: 100,
      });
      toast(`Import started! Task ID: ${data.task_id}`, "success");
      fetchLeads();
    } catch (err: any) { toast(err.message, "error"); }
    finally { setDiscoveryImporting(false); }
  }

  async function handleVerifyEmail() {
    setEmailVerify({ ...emailVerify, loading: true, result: null });
    try {
      const result = await api.discovery.verifyEmail(emailVerify.email);
      setEmailVerify({ ...emailVerify, loading: false, result });
    } catch (err: any) { setEmailVerify({ ...emailVerify, loading: false, result: { error: err.message } }); }
  }

  async function handleFindEmail() {
    setEmailFind({ ...emailFind, loading: true, result: null });
    try {
      const result = await api.discovery.findEmail(emailFind.domain, emailFind.firstName, emailFind.lastName);
      setEmailFind({ ...emailFind, loading: false, result });
    } catch (err: any) { setEmailFind({ ...emailFind, loading: false, result: { error: err.message } }); }
  }

  function toggleRole(role: string) {
    setDiscoveryForm({
      ...discoveryForm,
      job_titles: discoveryForm.job_titles.includes(role)
        ? discoveryForm.job_titles.filter((r) => r !== role)
        : [...discoveryForm.job_titles, role],
    });
  }

  function toggleIndustry(ind: string) {
    setDiscoveryForm({
      ...discoveryForm,
      industries: discoveryForm.industries.includes(ind)
        ? discoveryForm.industries.filter((i) => i !== ind)
        : [...discoveryForm.industries, ind],
    });
  }

  return (
    <div>
      <Header title="Leads" />

      {/* Controls */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 max-w-lg">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search leads..."
            className="flex-1 px-4 py-2 border border-rich-creme rounded text-sm bg-white focus:outline-none focus:border-crimson"
          />
          <Button type="submit" size="sm">
            Search
          </Button>
        </form>

        <div className="flex items-center gap-3">
          <select
            value={stageFilter}
            onChange={(e) => {
              setStageFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-rich-creme rounded text-sm bg-white focus:outline-none focus:border-crimson"
          >
            <option value="">All Stages</option>
            <option value="prospect">Prospect</option>
            <option value="contacted">Contacted</option>
            <option value="engaged">Engaged</option>
            <option value="qualified">Qualified</option>
            <option value="proposal_sent">Proposal Sent</option>
            <option value="negotiation">Negotiation</option>
            <option value="won">Won</option>
            <option value="lost">Lost</option>
          </select>

          <select
            value={emailFilter}
            onChange={(e) => {
              setEmailFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-rich-creme rounded text-sm bg-white focus:outline-none focus:border-crimson"
          >
            <option value="">All Leads</option>
            <option value="true">Has Email</option>
            <option value="false">Missing Email</option>
          </select>

          <Button variant="outline" size="sm" onClick={() => setShowAddForm(true)}>
            + Add Lead
          </Button>
          <Button variant="outline" size="sm" onClick={handleDiscover} disabled={generating}>
            {generating ? "Running..." : "Discover Now"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
          >
            Import CSV
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={handleImport}
            className="hidden"
          />
        </div>
      </div>

      {/* Import result */}
      {importResult && (
        <div
          className={`mb-4 p-4 rounded text-sm ${
            importResult.success
              ? "bg-green-50 text-green-800 border border-green-200"
              : "bg-red-50 text-red-800 border border-red-200"
          }`}
        >
          {importResult.success ? (
            <p>
              Imported {importResult.created} leads.
              {importResult.skipped_duplicates > 0 &&
                ` Skipped ${importResult.skipped_duplicates} duplicates.`}
              {importResult.errors?.length > 0 &&
                ` ${importResult.errors.length} errors.`}
            </p>
          ) : (
            <p>Import failed: {importResult.error}</p>
          )}
          <button
            onClick={() => setImportResult(null)}
            className="text-xs underline mt-1"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Add Lead Form */}
      {showAddForm && (
        <div className="mb-6 bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Add New Lead
          </h3>
          <form onSubmit={handleAddLead} className="grid grid-cols-2 gap-5">
            <input
              required
              placeholder="First Name *"
              value={newLead.first_name}
              onChange={(e) => setNewLead({ ...newLead, first_name: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <input
              required
              placeholder="Last Name *"
              value={newLead.last_name}
              onChange={(e) => setNewLead({ ...newLead, last_name: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <input
              placeholder="Email"
              type="email"
              value={newLead.email}
              onChange={(e) => setNewLead({ ...newLead, email: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <input
              required
              placeholder="Job Title *"
              value={newLead.job_title}
              onChange={(e) => setNewLead({ ...newLead, job_title: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <input
              placeholder="Phone"
              value={newLead.phone}
              onChange={(e) => setNewLead({ ...newLead, phone: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <select
              value={newLead.department}
              onChange={(e) => setNewLead({ ...newLead, department: e.target.value })}
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            >
              <option value="">Department</option>
              <option value="Procurement">Procurement</option>
              <option value="HR">HR</option>
              <option value="Admin">Admin</option>
              <option value="Marketing">Marketing</option>
              <option value="C-Suite">C-Suite</option>
              <option value="Other">Other</option>
            </select>
            <div className="col-span-2 flex gap-3">
              <Button type="submit" size="sm">
                Save Lead
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowAddForm(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Discovery Tools (collapsible) */}
      <div className="mb-6">
        <button
          onClick={() => setShowDiscovery(!showDiscovery)}
          className="flex items-center gap-2 text-sm font-bold text-crimson-dark hover:text-crimson transition-colors"
        >
          <span className="text-xs">{showDiscovery ? "▼" : "▶"}</span>
          Discovery Tools (Apollo, Email Finder, Scoring)
        </button>

        {showDiscovery && (
          <div className="mt-4 space-y-6">
            {/* Apollo Search */}
            <div className="bg-white rounded-xl p-6 border border-rich-creme">
              <h3 className="font-display text-base font-bold text-crimson-dark mb-4">Search Apollo.io</h3>
              <div className="mb-3">
                <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-2">Target Roles</label>
                <div className="flex flex-wrap gap-2">
                  {APEX_ROLES.map((role) => (
                    <button key={role} onClick={() => toggleRole(role)} className={`text-xs px-3 py-1.5 rounded border transition-colors ${discoveryForm.job_titles.includes(role) ? "bg-crimson text-white border-crimson" : "border-rich-creme text-warm-charcoal hover:border-crimson"}`}>
                      {role}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mb-3">
                <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-2">Industries</label>
                <div className="flex flex-wrap gap-2">
                  {APEX_INDUSTRIES.map((ind) => (
                    <button key={ind.value} onClick={() => toggleIndustry(ind.value)} className={`text-xs px-3 py-1.5 rounded border transition-colors ${discoveryForm.industries.includes(ind.value) ? "bg-crimson text-white border-crimson" : "border-rich-creme text-warm-charcoal hover:border-crimson"}`}>
                      {ind.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <div>
                  <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Location</label>
                  <input value={discoveryForm.locations.join(", ")} onChange={(e) => setDiscoveryForm({ ...discoveryForm, locations: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="India, Mumbai" className="w-full px-3 py-2 border border-rich-creme rounded text-sm" />
                </div>
                <div>
                  <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Company Size</label>
                  <select multiple value={discoveryForm.company_sizes} onChange={(e) => setDiscoveryForm({ ...discoveryForm, company_sizes: Array.from(e.target.selectedOptions, (o) => o.value) })} className="w-full px-3 py-2 border border-rich-creme rounded text-sm h-[38px]">
                    <option value="1-10">1-10</option><option value="11-50">11-50</option><option value="51-200">51-200</option>
                    <option value="201-500">201-500</option><option value="501-1000">501-1000</option><option value="1001-5000">1001-5000</option><option value="5001+">5001+</option>
                  </select>
                </div>
                <div>
                  <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Keywords</label>
                  <input value={discoveryForm.keywords} onChange={(e) => setDiscoveryForm({ ...discoveryForm, keywords: e.target.value })} placeholder="corporate gifting, apparel" className="w-full px-3 py-2 border border-rich-creme rounded text-sm" />
                </div>
              </div>
              <div className="flex gap-3">
                <Button size="sm" onClick={handleDiscoverySearch} disabled={discoverySearching}>{discoverySearching ? "Searching..." : "Search Apollo.io"}</Button>
                <Button size="sm" variant="outline" onClick={handleDiscoveryImport} disabled={discoveryImporting}>{discoveryImporting ? "Importing..." : "Bulk Import (up to 100)"}</Button>
                <Button size="sm" variant="outline" onClick={() => api.discovery.batchScore()}>Score All Unscored</Button>
              </div>
            </div>

            {/* Search Results */}
            {discoveryResults.length > 0 && (
              <div className="bg-white rounded-xl border border-rich-creme overflow-hidden">
                <div className="px-5 py-3 bg-creme/50 border-b border-rich-creme">
                  <p className="text-sm font-bold text-warm-charcoal">{discoveryTotal.toLocaleString()} results found</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-rich-creme">
                        <th className="text-left px-5 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Name</th>
                        <th className="text-left px-5 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Title</th>
                        <th className="text-left px-5 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Company</th>
                        <th className="text-left px-5 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Industry</th>
                        <th className="text-left px-5 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Email</th>
                        <th className="text-left px-5 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">City</th>
                      </tr>
                    </thead>
                    <tbody>
                      {discoveryResults.map((person, i) => (
                        <tr key={i} className="border-b border-rich-creme/50 hover:bg-creme/30">
                          <td className="px-5 py-3 text-sm font-bold text-warm-charcoal max-w-[150px] truncate">{person.name}</td>
                          <td className="px-5 py-3 text-sm text-warm-charcoal max-w-[150px] truncate">{person.title}</td>
                          <td className="px-5 py-3 text-sm text-warm-charcoal max-w-[150px] truncate">{person.company?.name}</td>
                          <td className="px-5 py-3"><Badge variant="default">{person.company?.industry || "—"}</Badge></td>
                          <td className="px-5 py-3 text-sm font-mono text-warm-charcoal max-w-[160px] truncate">{person.email || <span className="text-mid-warm italic">hidden</span>}</td>
                          <td className="px-5 py-3 text-xs text-mid-warm">{person.city}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Email Tools */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white rounded-xl p-5 border border-rich-creme">
                <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Email Verification (Hunter.io)</h3>
                <div className="flex gap-2 mb-2">
                  <input value={emailVerify.email} onChange={(e) => setEmailVerify({ ...emailVerify, email: e.target.value })} placeholder="email@example.com" className="flex-1 px-3 py-2 border border-rich-creme rounded text-sm" />
                  <Button size="sm" onClick={handleVerifyEmail} disabled={emailVerify.loading || !emailVerify.email}>{emailVerify.loading ? "..." : "Verify"}</Button>
                </div>
                {emailVerify.result && (
                  <div className="text-sm">
                    <Badge variant={emailVerify.result.status === "valid" ? "success" : emailVerify.result.status === "invalid" ? "crimson" : "warning"}>{emailVerify.result.status}</Badge>
                    <span className="ml-2 text-mid-warm">Score: {emailVerify.result.score}/100</span>
                  </div>
                )}
              </div>
              <div className="bg-white rounded-xl p-5 border border-rich-creme">
                <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">Email Finder (Hunter.io)</h3>
                <div className="grid grid-cols-3 gap-2 mb-2">
                  <input value={emailFind.domain} onChange={(e) => setEmailFind({ ...emailFind, domain: e.target.value })} placeholder="company.com" className="px-3 py-2 border border-rich-creme rounded text-sm" />
                  <input value={emailFind.firstName} onChange={(e) => setEmailFind({ ...emailFind, firstName: e.target.value })} placeholder="First name" className="px-3 py-2 border border-rich-creme rounded text-sm" />
                  <input value={emailFind.lastName} onChange={(e) => setEmailFind({ ...emailFind, lastName: e.target.value })} placeholder="Last name" className="px-3 py-2 border border-rich-creme rounded text-sm" />
                </div>
                <Button size="sm" onClick={handleFindEmail} disabled={emailFind.loading || !emailFind.domain}>{emailFind.loading ? "..." : "Find Email"}</Button>
                {emailFind.result && emailFind.result.email && (
                  <div className="mt-2 text-sm"><span className="font-mono text-warm-charcoal">{emailFind.result.email}</span> <span className="text-mid-warm">Score: {emailFind.result.score}/100</span></div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Stats bar */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-mid-warm">
          {loading ? "Loading..." : `${total} leads found`}
        </p>
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              Prev
            </Button>
            <span className="text-sm text-mid-warm">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </div>

      {/* Lead Table */}
      {!loading && <LeadTable leads={leads} onEdit={openEditLead} onDelete={handleDeleteLead} />}

      {/* Edit Lead Modal */}
      {editingLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="font-display text-lg font-bold text-crimson-dark mb-4">Edit Lead</h2>
            <form onSubmit={handleEditLead} className="space-y-3">
              <input
                required
                placeholder="First Name *"
                value={editForm.first_name}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
              />
              <input
                required
                placeholder="Last Name *"
                value={editForm.last_name}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
              />
              <input
                placeholder="Email"
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
              />
              <input
                required
                placeholder="Job Title *"
                value={editForm.job_title}
                onChange={(e) => setEditForm({ ...editForm, job_title: e.target.value })}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
              />
              <input
                placeholder="Phone"
                value={editForm.phone}
                onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
              />
              <select
                value={editForm.department}
                onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
                className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
              >
                <option value="">Department</option>
                <option value="Procurement">Procurement</option>
                <option value="HR">HR</option>
                <option value="Admin">Admin</option>
                <option value="Marketing">Marketing</option>
                <option value="C-Suite">C-Suite</option>
                <option value="Other">Other</option>
              </select>
              <div className="flex gap-2 justify-end mt-4">
                <Button variant="outline" size="sm" type="button" onClick={() => setEditingLead(null)}>Cancel</Button>
                <Button size="sm" type="submit" disabled={editSaving}>{editSaving ? "Saving..." : "Save Changes"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
