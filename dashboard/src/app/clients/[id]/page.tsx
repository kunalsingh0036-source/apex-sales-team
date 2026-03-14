"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import {
  Client, ClientContact, BrandAsset, Interaction, SampleKit,
  AMA_TIER_LABELS, AMA_TIER_COLORS, AMATier,
} from "@/lib/types";
import { clsx } from "clsx";

type Tab = "overview" | "contacts" | "interactions" | "brand_assets" | "sample_kits";

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<Client | null>(null);
  const [revenue, setRevenue] = useState<any>(null);
  const [contacts, setContacts] = useState<ClientContact[]>([]);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [brandAssets, setBrandAssets] = useState<BrandAsset[]>([]);
  const [sampleKits, setSampleKits] = useState<SampleKit[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [c, r] = await Promise.all([
          api.clients.get(id),
          api.clients.revenue(id),
        ]);
        setClient(c);
        setRevenue(r);
      } catch (err) {
        console.error("Failed to load client:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  useEffect(() => {
    if (activeTab === "contacts") {
      api.clients.contacts(id).then(setContacts).catch(console.error);
    } else if (activeTab === "interactions") {
      api.clients.interactions(id).then(setInteractions).catch(console.error);
    } else if (activeTab === "brand_assets") {
      api.clients.brandAssets(id).then(setBrandAssets).catch(console.error);
    } else if (activeTab === "sample_kits") {
      api.clients.sampleKits(id).then(setSampleKits).catch(console.error);
    }
  }, [activeTab, id]);

  if (loading) {
    return (
      <div>
        <Header title="Client Details" />
        <p className="text-mid-warm">Loading...</p>
      </div>
    );
  }

  if (!client) {
    return (
      <div>
        <Header title="Client Details" />
        <p className="text-mid-warm">Client not found</p>
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "contacts", label: "Contacts" },
    { key: "interactions", label: "Interactions" },
    { key: "brand_assets", label: "Brand Assets" },
    { key: "sample_kits", label: "Sample Kits" },
  ];

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

  return (
    <div>
      <Header title={client.primary_contact_name} />

      {/* Client Header Card */}
      <div className="bg-white rounded-lg border border-rich-creme p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-display text-xl font-bold text-crimson-dark">
              {client.primary_contact_name}
            </h3>
            {client.primary_contact_title && (
              <p className="text-sm text-mid-warm mt-1">{client.primary_contact_title}</p>
            )}
            <div className="flex items-center gap-4 mt-3 text-sm text-warm-charcoal">
              {client.primary_contact_email && <span>{client.primary_contact_email}</span>}
              {client.primary_contact_phone && <span>{client.primary_contact_phone}</span>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={client.status === "active" ? "success" : "default"}>{client.status}</Badge>
            {client.ama_tier && (
              <span className={clsx("inline-flex items-center px-3 py-1 rounded-full text-xs font-bold", AMA_TIER_COLORS[client.ama_tier as AMATier])}>
                {AMA_TIER_LABELS[client.ama_tier as AMATier]} AMA
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Revenue Summary */}
      {revenue && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg border border-rich-creme p-4">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Orders</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{revenue.total_orders}</p>
          </div>
          <div className="bg-white rounded-lg border border-rich-creme p-4">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Spend</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{formatCurrency(revenue.total_spend)}</p>
          </div>
          <div className="bg-white rounded-lg border border-rich-creme p-4">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">AMA Commitment</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{formatCurrency(revenue.ama_commitment)}</p>
          </div>
          <div className="bg-white rounded-lg border border-rich-creme p-4">
            <p className="font-label text-xs tracking-wider text-mid-warm uppercase">AMA Utilization</p>
            <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{revenue.ama_utilization}%</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-rich-creme mb-6">
        <div className="flex gap-0">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={clsx(
                "px-4 py-3 text-sm font-bold border-b-2 transition-colors -mb-px",
                activeTab === tab.key
                  ? "border-crimson text-crimson"
                  : "border-transparent text-mid-warm hover:text-warm-charcoal"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-lg border border-rich-creme p-6">
            <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-4">Details</h4>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-mid-warm">GST Number</dt>
                <dd className="text-warm-charcoal font-bold">{client.gst_number || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-mid-warm">Payment Terms</dt>
                <dd className="text-warm-charcoal font-bold">{client.payment_terms || "—"}</dd>
              </div>
              {client.tags.length > 0 && (
                <div className="flex justify-between">
                  <dt className="text-mid-warm">Tags</dt>
                  <dd className="flex gap-1 flex-wrap">
                    {client.tags.map((t) => (
                      <Badge key={t}>{t}</Badge>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </div>
          <div className="bg-white rounded-lg border border-rich-creme p-6">
            <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-4">Addresses</h4>
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-mid-warm mb-1">Billing</p>
                <p className="text-warm-charcoal whitespace-pre-line">{client.billing_address || "—"}</p>
              </div>
              <div>
                <p className="text-mid-warm mb-1">Shipping</p>
                <p className="text-warm-charcoal whitespace-pre-line">{client.shipping_address || "—"}</p>
              </div>
            </div>
          </div>
          {client.notes && (
            <div className="col-span-2 bg-white rounded-lg border border-rich-creme p-6">
              <h4 className="font-label text-xs tracking-wider text-mid-warm uppercase mb-4">Notes</h4>
              <p className="text-sm text-warm-charcoal whitespace-pre-line">{client.notes}</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "contacts" && (
        <div className="bg-white rounded-lg border border-rich-creme overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rich-creme bg-creme/30">
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Name</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Email</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Phone</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Title</th>
                <th className="text-left px-4 py-3 font-label text-xs tracking-wider text-mid-warm uppercase">Primary</th>
              </tr>
            </thead>
            <tbody>
              {contacts.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-mid-warm">No contacts</td></tr>
              ) : contacts.map((c) => (
                <tr key={c.id} className="border-b border-rich-creme/50">
                  <td className="px-4 py-3 font-bold text-warm-charcoal">{c.name}</td>
                  <td className="px-4 py-3">{c.email || "—"}</td>
                  <td className="px-4 py-3">{c.phone || "—"}</td>
                  <td className="px-4 py-3">{c.title || "—"}</td>
                  <td className="px-4 py-3">{c.is_primary ? <Badge variant="crimson">Primary</Badge> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "interactions" && (
        <div className="space-y-4">
          {interactions.length === 0 ? (
            <p className="text-mid-warm text-center py-8">No interactions recorded</p>
          ) : interactions.map((i) => (
            <div key={i.id} className="bg-white rounded-lg border border-rich-creme p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge variant="info">{i.type}</Badge>
                    <span className="font-bold text-sm text-warm-charcoal">{i.subject}</span>
                  </div>
                  {i.description && <p className="text-sm text-mid-warm mt-2">{i.description}</p>}
                </div>
                <span className="text-xs text-mid-warm">
                  {new Date(i.interaction_date).toLocaleDateString("en-IN")}
                </span>
              </div>
              {i.follow_up_date && (
                <p className="text-xs text-crimson mt-2">Follow-up: {new Date(i.follow_up_date).toLocaleDateString("en-IN")}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {activeTab === "brand_assets" && (
        <div className="grid grid-cols-3 gap-4">
          {brandAssets.length === 0 ? (
            <p className="col-span-3 text-mid-warm text-center py-8">No brand assets</p>
          ) : brandAssets.map((a) => (
            <div key={a.id} className="bg-white rounded-lg border border-rich-creme p-4">
              <Badge>{a.asset_type}</Badge>
              <p className="font-bold text-sm text-warm-charcoal mt-2">{a.name}</p>
              {a.value && <p className="text-sm text-mid-warm mt-1">{a.value}</p>}
              {a.notes && <p className="text-xs text-mid-warm mt-2">{a.notes}</p>}
            </div>
          ))}
        </div>
      )}

      {activeTab === "sample_kits" && (
        <div className="space-y-4">
          {sampleKits.length === 0 ? (
            <p className="text-mid-warm text-center py-8">No sample kits</p>
          ) : sampleKits.map((kit) => (
            <div key={kit.id} className="bg-white rounded-lg border border-rich-creme p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-bold text-sm text-warm-charcoal">{kit.kit_name}</span>
                  <p className="text-xs text-mid-warm mt-1">To: {kit.recipient_name}</p>
                </div>
                <Badge variant={kit.status === "delivered" ? "success" : kit.status === "preparing" ? "warning" : "info"}>
                  {kit.status}
                </Badge>
              </div>
              {kit.tracking_number && (
                <p className="text-xs text-mid-warm mt-2">Tracking: {kit.tracking_number}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
