"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";

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
  company: {
    name: string;
    domain: string;
    industry: string;
    employee_count: number | null;
  };
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

export default function DiscoveryPage() {
  const [searchType, setSearchType] = useState<"people" | "companies">("people");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<PersonResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [selectedForImport, setSelectedForImport] = useState<Set<number>>(new Set());
  const { toast } = useToast();
  const [importing, setImporting] = useState(false);

  const [form, setForm] = useState({
    job_titles: [] as string[],
    industries: [] as string[],
    locations: ["India"],
    company_sizes: [] as string[],
    keywords: "",
  });

  const [emailVerify, setEmailVerify] = useState({ email: "", result: null as any, loading: false });
  const [emailFind, setEmailFind] = useState({ domain: "", firstName: "", lastName: "", result: null as any, loading: false });

  async function handleSearch() {
    setSearching(true);
    setResults([]);
    try {
      const data = await api.discovery.searchPeople({
        job_titles: form.job_titles.length > 0 ? form.job_titles : undefined,
        industries: form.industries.length > 0 ? form.industries : undefined,
        locations: form.locations.length > 0 ? form.locations : undefined,
        company_sizes: form.company_sizes.length > 0 ? form.company_sizes : undefined,
        keywords: form.keywords ? form.keywords.split(",").map((k: string) => k.trim()) : undefined,
      });
      setResults(data.people || []);
      setTotalResults(data.total || 0);
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setSearching(false);
    }
  }

  async function handleBulkImport() {
    setImporting(true);
    try {
      const data = await api.discovery.importFromApollo({
        job_titles: form.job_titles.length > 0 ? form.job_titles : undefined,
        industries: form.industries.length > 0 ? form.industries : undefined,
        locations: form.locations,
        company_sizes: form.company_sizes.length > 0 ? form.company_sizes : undefined,
        keywords: form.keywords ? form.keywords.split(",").map((k: string) => k.trim()) : undefined,
        max_results: 100,
      });
      toast(`Import started! Task ID: ${data.task_id}`, "success");
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setImporting(false);
    }
  }

  async function handleVerifyEmail() {
    setEmailVerify({ ...emailVerify, loading: true, result: null });
    try {
      const result = await api.discovery.verifyEmail(emailVerify.email);
      setEmailVerify({ ...emailVerify, loading: false, result });
    } catch (err: any) {
      setEmailVerify({ ...emailVerify, loading: false, result: { error: err.message } });
    }
  }

  async function handleFindEmail() {
    setEmailFind({ ...emailFind, loading: true, result: null });
    try {
      const result = await api.discovery.findEmail(emailFind.domain, emailFind.firstName, emailFind.lastName);
      setEmailFind({ ...emailFind, loading: false, result });
    } catch (err: any) {
      setEmailFind({ ...emailFind, loading: false, result: { error: err.message } });
    }
  }

  function toggleRole(role: string) {
    setForm({
      ...form,
      job_titles: form.job_titles.includes(role)
        ? form.job_titles.filter((r) => r !== role)
        : [...form.job_titles, role],
    });
  }

  function toggleIndustry(ind: string) {
    setForm({
      ...form,
      industries: form.industries.includes(ind)
        ? form.industries.filter((i) => i !== ind)
        : [...form.industries, ind],
    });
  }

  return (
    <div>
      <Header title="Lead Discovery" />

      {/* Search Panel */}
      <div className="bg-white rounded-xl p-7 border border-rich-creme mb-6">
        <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
          Search for Leads (Apollo.io)
        </h3>

        {/* Job Titles */}
        <div className="mb-4">
          <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-2">
            Target Roles
          </label>
          <div className="flex flex-wrap gap-2">
            {APEX_ROLES.map((role) => (
              <button
                key={role}
                onClick={() => toggleRole(role)}
                className={`text-sm px-3.5 py-2 rounded border transition-colors ${
                  form.job_titles.includes(role)
                    ? "bg-crimson text-white border-crimson"
                    : "border-rich-creme text-warm-charcoal hover:border-crimson"
                }`}
              >
                {role}
              </button>
            ))}
          </div>
        </div>

        {/* Industries */}
        <div className="mb-4">
          <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-2">
            Industries
          </label>
          <div className="flex flex-wrap gap-2">
            {APEX_INDUSTRIES.map((ind) => (
              <button
                key={ind.value}
                onClick={() => toggleIndustry(ind.value)}
                className={`text-sm px-3.5 py-2 rounded border transition-colors ${
                  form.industries.includes(ind.value)
                    ? "bg-crimson text-white border-crimson"
                    : "border-rich-creme text-warm-charcoal hover:border-crimson"
                }`}
              >
                {ind.label}
              </button>
            ))}
          </div>
        </div>

        {/* Location & Size */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Location</label>
            <input
              value={form.locations.join(", ")}
              onChange={(e) => setForm({ ...form, locations: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
              placeholder="India, Mumbai"
              className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
            />
          </div>
          <div>
            <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Company Size</label>
            <select
              multiple
              value={form.company_sizes}
              onChange={(e) => setForm({ ...form, company_sizes: Array.from(e.target.selectedOptions, (o) => o.value) })}
              className="w-full px-3 py-2 border border-rich-creme rounded text-sm h-[38px]"
            >
              <option value="1-10">1-10</option>
              <option value="11-50">11-50</option>
              <option value="51-200">51-200</option>
              <option value="201-500">201-500</option>
              <option value="501-1000">501-1000</option>
              <option value="1001-5000">1001-5000</option>
              <option value="5001+">5001+</option>
            </select>
          </div>
          <div>
            <label className="font-label text-xs tracking-wider text-mid-warm uppercase block mb-1">Keywords</label>
            <input
              value={form.keywords}
              onChange={(e) => setForm({ ...form, keywords: e.target.value })}
              placeholder="corporate gifting, apparel"
              className="w-full px-3 py-2 border border-rich-creme rounded text-sm"
            />
          </div>
        </div>

        <div className="flex gap-3">
          <Button size="sm" onClick={handleSearch} disabled={searching}>
            {searching ? "Searching..." : "Search Apollo.io"}
          </Button>
          <Button size="sm" variant="outline" onClick={handleBulkImport} disabled={importing}>
            {importing ? "Importing..." : "Bulk Import (up to 100)"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => api.discovery.batchScore()}>
            Score All Unscored Leads
          </Button>
        </div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="bg-white rounded-xl border border-rich-creme overflow-hidden mb-6">
          <div className="px-5 py-3.5 bg-creme/50 border-b border-rich-creme flex justify-between items-center">
            <p className="text-sm font-bold text-warm-charcoal">
              {totalResults.toLocaleString()} results found
            </p>
          </div>
          <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-rich-creme">
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Name</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Title</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Company</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Industry</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">Email</th>
                <th className="text-left px-5 py-3.5 font-label text-xs tracking-wider text-mid-warm uppercase">City</th>
              </tr>
            </thead>
            <tbody>
              {results.map((person, i) => (
                <tr key={i} className="border-b border-rich-creme/50 hover:bg-creme/30">
                  <td className="px-5 py-3.5 text-sm font-bold text-warm-charcoal max-w-[150px] truncate">
                    {person.name}
                    {person.linkedin_url && (
                      <span className="text-sky-600 ml-1 text-xs">in</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-sm text-warm-charcoal max-w-[150px] truncate">{person.title}</td>
                  <td className="px-5 py-3.5 text-sm text-warm-charcoal max-w-[150px] truncate">
                    {person.company?.name}
                    {person.company?.employee_count && (
                      <span className="text-xs text-mid-warm ml-1">
                        ({person.company.employee_count})
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <Badge variant="default">{person.company?.industry || "—"}</Badge>
                  </td>
                  <td className="px-5 py-3.5 text-sm font-mono text-warm-charcoal max-w-[160px] truncate">
                    {person.email || <span className="text-mid-warm italic">hidden</span>}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-mid-warm">{person.city}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* Tools row */}
      <div className="grid grid-cols-2 gap-6">
        {/* Email Verification */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">
            Email Verification (Hunter.io)
          </h3>
          <div className="flex gap-2 mb-3">
            <input
              value={emailVerify.email}
              onChange={(e) => setEmailVerify({ ...emailVerify, email: e.target.value })}
              placeholder="email@example.com"
              className="flex-1 px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <Button size="sm" onClick={handleVerifyEmail} disabled={emailVerify.loading || !emailVerify.email}>
              {emailVerify.loading ? "..." : "Verify"}
            </Button>
          </div>
          {emailVerify.result && (
            <div className="text-sm">
              <Badge variant={emailVerify.result.status === "valid" ? "success" : emailVerify.result.status === "invalid" ? "crimson" : "warning"}>
                {emailVerify.result.status}
              </Badge>
              <span className="ml-2 text-mid-warm">Score: {emailVerify.result.score}/100</span>
            </div>
          )}
        </div>

        {/* Email Finder */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-3">
            Email Finder (Hunter.io)
          </h3>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <input
              value={emailFind.domain}
              onChange={(e) => setEmailFind({ ...emailFind, domain: e.target.value })}
              placeholder="company.com"
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <input
              value={emailFind.firstName}
              onChange={(e) => setEmailFind({ ...emailFind, firstName: e.target.value })}
              placeholder="First name"
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
            <input
              value={emailFind.lastName}
              onChange={(e) => setEmailFind({ ...emailFind, lastName: e.target.value })}
              placeholder="Last name"
              className="px-3 py-2 border border-rich-creme rounded text-sm"
            />
          </div>
          <Button size="sm" onClick={handleFindEmail} disabled={emailFind.loading || !emailFind.domain}>
            {emailFind.loading ? "..." : "Find Email"}
          </Button>
          {emailFind.result && emailFind.result.email && (
            <div className="mt-2 text-sm">
              <span className="font-mono text-warm-charcoal">{emailFind.result.email}</span>
              <span className="ml-2 text-mid-warm">Score: {emailFind.result.score}/100</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
