"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";
import { Client, PaginatedResponse, AMA_TIER_LABELS, AMA_TIER_COLORS, AMATier } from "@/lib/types";
import { clsx } from "clsx";

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [amaFilter, setAmaFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ primary_contact_name: "", primary_contact_email: "", primary_contact_phone: "", primary_contact_title: "", company_name: "", ama_tier: "bronze" });
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [editForm, setEditForm] = useState({ primary_contact_name: "", primary_contact_email: "", primary_contact_phone: "", primary_contact_title: "", ama_tier: "bronze" });
  const [editSaving, setEditSaving] = useState(false);

  async function fetchClients() {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: 50 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (amaFilter) params.ama_tier = amaFilter;
      const data: PaginatedResponse<Client> = await api.clients.list(params);
      setClients(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      console.error("Failed to fetch clients:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchClients();
  }, [page, statusFilter, amaFilter]);

  async function handleAddClient(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      // Create or find company first
      const company = await api.companies.create({ name: form.company_name, industry: "" });
      const companyId = company.id;
      await api.clients.create({
        company_id: companyId,
        primary_contact_name: form.primary_contact_name,
        primary_contact_email: form.primary_contact_email || undefined,
        primary_contact_phone: form.primary_contact_phone || undefined,
        primary_contact_title: form.primary_contact_title || undefined,
        ama_tier: form.ama_tier,
      });
      setShowModal(false);
      setForm({ primary_contact_name: "", primary_contact_email: "", primary_contact_phone: "", primary_contact_title: "", company_name: "", ama_tier: "bronze" });
      toast("Client added.", "success");
      fetchClients();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setSaving(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchClients();
  }

  function openEditClient(client: Client) {
    setEditingClient(client);
    setEditForm({
      primary_contact_name: client.primary_contact_name,
      primary_contact_email: client.primary_contact_email || "",
      primary_contact_phone: client.primary_contact_phone || "",
      primary_contact_title: client.primary_contact_title || "",
      ama_tier: client.ama_tier || "bronze",
    });
  }

  async function handleEditClient(e: React.FormEvent) {
    e.preventDefault();
    if (!editingClient) return;
    setEditSaving(true);
    try {
      await api.clients.update(editingClient.id, editForm);
      toast("Client updated.", "success");
      setEditingClient(null);
      fetchClients();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDeleteClient(client: Client) {
    if (!confirm(`Delete client "${client.primary_contact_name}"? This cannot be undone.`)) return;
    try {
      await api.clients.delete(client.id);
      toast("Client deleted.", "success");
      fetchClients();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <Header title="Clients" />
        <Button size="sm" onClick={() => setShowModal(true)}>+ Add Client</Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-xl border border-rich-creme p-5">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Clients</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{total}</p>
        </div>
        {(["bronze", "silver", "gold", "institutional"] as AMATier[]).map((tier) => (
          <div key={tier} className="bg-white rounded-xl border border-rich-creme p-5">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">{AMA_TIER_LABELS[tier]}</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">
              {clients.filter((c) => c.ama_tier === tier).length}
            </p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <form onSubmit={handleSearch} className="flex-1 flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search clients..."
            className="flex-1 px-4 py-2 rounded border border-rich-creme bg-white text-sm focus:outline-none focus:border-crimson"
          />
          <Button type="submit" size="sm">Search</Button>
        </form>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded border border-rich-creme bg-white text-sm"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="churned">Churned</option>
        </select>
        <select
          value={amaFilter}
          onChange={(e) => { setAmaFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded border border-rich-creme bg-white text-sm"
        >
          <option value="">All AMA Tiers</option>
          <option value="bronze">Bronze</option>
          <option value="silver">Silver</option>
          <option value="gold">Gold</option>
          <option value="institutional">Institutional</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-rich-creme overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rich-creme bg-creme/30">
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Contact</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Email</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">AMA Tier</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Status</th>
              <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Created</th>
              <th className="text-right px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-mid-warm">Loading...</td>
              </tr>
            ) : clients.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-mid-warm">No clients found</td>
              </tr>
            ) : (
              clients.map((client) => (
                <tr key={client.id} className="border-b border-rich-creme/50 hover:bg-creme/20 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/clients/${client.id}`} className="font-bold text-crimson-dark hover:text-crimson truncate block">
                      {client.primary_contact_name}
                    </Link>
                    {client.primary_contact_title && (
                      <p className="text-xs text-mid-warm mt-0.5">{client.primary_contact_title}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-warm-charcoal truncate max-w-[200px]">{client.primary_contact_email || "—"}</td>
                  <td className="px-4 py-3">
                    {client.ama_tier ? (
                      <span className={clsx("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold", AMA_TIER_COLORS[client.ama_tier as AMATier])}>
                        {AMA_TIER_LABELS[client.ama_tier as AMATier]}
                      </span>
                    ) : (
                      <span className="text-mid-warm">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={client.status === "active" ? "success" : "default"}>
                      {client.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-mid-warm">
                    {new Date(client.created_at).toLocaleDateString("en-IN")}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => openEditClient(client)}
                        className="text-xs px-2.5 py-1 rounded border border-rich-creme text-crimson-dark hover:bg-creme/50 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteClient(client)}
                        className="text-xs px-2.5 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-mid-warm">
            Showing {(page - 1) * 50 + 1}-{Math.min(page * 50, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold mb-4">Add Client</h2>
            <form onSubmit={handleAddClient} className="space-y-3">
              <input type="text" placeholder="Contact Name *" required value={form.primary_contact_name} onChange={(e) => setForm({ ...form, primary_contact_name: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="email" placeholder="Email" value={form.primary_contact_email} onChange={(e) => setForm({ ...form, primary_contact_email: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="text" placeholder="Phone" value={form.primary_contact_phone} onChange={(e) => setForm({ ...form, primary_contact_phone: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="text" placeholder="Title / Role" value={form.primary_contact_title} onChange={(e) => setForm({ ...form, primary_contact_title: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="text" placeholder="Company Name *" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <select value={form.ama_tier} onChange={(e) => setForm({ ...form, ama_tier: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson">
                <option value="bronze">Bronze</option>
                <option value="silver">Silver</option>
                <option value="gold">Gold</option>
                <option value="institutional">Institutional</option>
              </select>
              <div className="flex gap-2 justify-end mt-4">
                <Button variant="outline" size="sm" type="button" onClick={() => setShowModal(false)}>Cancel</Button>
                <Button size="sm" type="submit" disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Client Modal */}
      {editingClient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold mb-4">Edit Client</h2>
            <form onSubmit={handleEditClient} className="space-y-3">
              <input
                type="text"
                placeholder="Contact Name *"
                required
                value={editForm.primary_contact_name}
                onChange={(e) => setEditForm({ ...editForm, primary_contact_name: e.target.value })}
                className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson"
              />
              <input
                type="email"
                placeholder="Email"
                value={editForm.primary_contact_email}
                onChange={(e) => setEditForm({ ...editForm, primary_contact_email: e.target.value })}
                className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson"
              />
              <input
                type="text"
                placeholder="Phone"
                value={editForm.primary_contact_phone}
                onChange={(e) => setEditForm({ ...editForm, primary_contact_phone: e.target.value })}
                className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson"
              />
              <input
                type="text"
                placeholder="Title / Role"
                value={editForm.primary_contact_title}
                onChange={(e) => setEditForm({ ...editForm, primary_contact_title: e.target.value })}
                className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson"
              />
              <select
                value={editForm.ama_tier}
                onChange={(e) => setEditForm({ ...editForm, ama_tier: e.target.value })}
                className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson"
              >
                <option value="bronze">Bronze</option>
                <option value="silver">Silver</option>
                <option value="gold">Gold</option>
                <option value="institutional">Institutional</option>
              </select>
              <div className="flex gap-2 justify-end mt-4">
                <Button variant="outline" size="sm" type="button" onClick={() => setEditingClient(null)}>Cancel</Button>
                <Button size="sm" type="submit" disabled={editSaving}>{editSaving ? "Saving..." : "Save Changes"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
