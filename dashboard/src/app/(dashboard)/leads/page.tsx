"use client";

import { useEffect, useState, useRef } from "react";
import Header from "@/components/layout/Header";
import LeadTable from "@/components/leads/LeadTable";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { Lead, PaginatedResponse, INDUSTRIES, SENIORITY_LEVELS } from "@/lib/types";

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [generating, setGenerating] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
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
  }, [page, stageFilter]);

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
      alert(JSON.stringify(result, null, 2));
      fetchLeads();
    } catch (err: any) {
      alert("Failed: " + err.message);
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
      alert("Failed to create lead: " + err.message);
    }
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
      {!loading && <LeadTable leads={leads} />}
    </div>
  );
}
