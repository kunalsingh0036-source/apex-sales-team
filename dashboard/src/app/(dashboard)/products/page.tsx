"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";
import { Product, ProductCategory, PaginatedResponse } from "@/lib/types";

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", sku: "", category: "", base_price: "", moq: "", gsm: "", description: "" });

  async function fetchData() {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: 50 };
      if (search) params.search = search;
      if (categoryFilter) params.category_id = categoryFilter;
      const [data, cats] = await Promise.all([
        api.products.list(params),
        api.products.categories(),
      ]);
      setProducts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setCategories(cats);
    } catch (err) {
      console.error("Failed to fetch products:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, [page, categoryFilter]);

  async function handleAddProduct(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.products.create({
        ...form,
        base_price: form.base_price ? Number(form.base_price) : undefined,
        moq: form.moq ? Number(form.moq) : undefined,
        gsm: form.gsm ? Number(form.gsm) : undefined,
      });
      setShowModal(false);
      setForm({ name: "", sku: "", category: "", base_price: "", moq: "", gsm: "", description: "" });
      fetchData();
    } catch (err) {
      console.error("Failed to create product:", err);
    } finally {
      setSaving(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchData();
  }

  const formatCurrency = (val: number | null) =>
    val != null
      ? new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val)
      : "—";

  const getCategoryName = (id: string) =>
    categories.find((c) => c.id === id)?.name || "—";

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <Header title="Product Catalogue" />
        <Button size="sm" onClick={() => setShowModal(true)}>+ Add Product</Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-xl border border-rich-creme p-5">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Total Products</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{total}</p>
        </div>
        <div className="bg-white rounded-xl border border-rich-creme p-5">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Categories</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">{categories.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-rich-creme p-5">
          <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Active Products</p>
          <p className="font-display text-2xl font-bold text-crimson-dark mt-1">
            {products.filter((p) => p.is_active).length}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <form onSubmit={handleSearch} className="flex-1 flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products..."
            className="flex-1 px-4 py-2 rounded border border-rich-creme bg-white text-sm focus:outline-none focus:border-crimson"
          />
          <Button type="submit" size="sm">Search</Button>
        </form>
        <select
          value={categoryFilter}
          onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded border border-rich-creme bg-white text-sm"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>{cat.name}</option>
          ))}
        </select>
      </div>

      {/* Product Grid */}
      {loading ? (
        <p className="text-mid-warm text-center py-8">Loading...</p>
      ) : products.length === 0 ? (
        <p className="text-mid-warm text-center py-8">No products found</p>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {products.map((product) => (
            <div key={product.id} className="bg-white rounded-xl border border-rich-creme p-5 hover:shadow transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-bold text-sm text-crimson-dark truncate">{product.name}</h3>
                  {product.sku && <p className="text-xs text-mid-warm mt-0.5 truncate">SKU: {product.sku}</p>}
                </div>
                <Badge variant={product.is_active ? "success" : "default"}>
                  {product.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>

              <p className="text-xs text-mid-warm mb-3 truncate">{getCategoryName(product.category_id)}</p>

              {product.description && (
                <p className="text-xs text-warm-charcoal mb-3 line-clamp-2">{product.description}</p>
              )}

              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-mid-warm">Base Price</span>
                  <span className="font-bold text-warm-charcoal">{formatCurrency(product.base_price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-mid-warm">MOQ</span>
                  <span className="font-bold text-warm-charcoal">{product.min_order_qty}</span>
                </div>
                {product.gsm_range && (
                  <div className="flex justify-between">
                    <span className="text-mid-warm">GSM</span>
                    <span className="font-bold text-warm-charcoal">{product.gsm_range}</span>
                  </div>
                )}
                {product.lead_time_days && (
                  <div className="flex justify-between">
                    <span className="text-mid-warm">Lead Time</span>
                    <span className="font-bold text-warm-charcoal">{product.lead_time_days} days</span>
                  </div>
                )}
              </div>

              {(product.available_sizes.length > 0 || product.available_colors.length > 0) && (
                <div className="mt-3 flex gap-1 flex-wrap">
                  {product.available_sizes.slice(0, 5).map((s) => (
                    <span key={s} className="inline-flex items-center px-1.5 py-0.5 rounded bg-rich-creme text-[10px] text-warm-charcoal">{s}</span>
                  ))}
                  {product.available_colors.slice(0, 3).map((c) => (
                    <span key={c} className="inline-flex items-center px-1.5 py-0.5 rounded bg-rich-creme text-[10px] text-warm-charcoal">{c}</span>
                  ))}
                </div>
              )}

              {product.available_customizations.length > 0 && (
                <div className="mt-2">
                  <p className="text-[10px] text-mid-warm uppercase tracking-wider">Customizations</p>
                  <div className="flex gap-1 flex-wrap mt-1">
                    {product.available_customizations.map((c) => (
                      <Badge key={c}>{c}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-mid-warm">
            Showing {(page - 1) * 50 + 1}-{Math.min(page * 50, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold mb-4">Add Product</h2>
            <form onSubmit={handleAddProduct} className="space-y-3">
              <input type="text" placeholder="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="text" placeholder="SKU" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="text" placeholder="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="number" placeholder="Base Price" value={form.base_price} onChange={(e) => setForm({ ...form, base_price: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="number" placeholder="MOQ" value={form.moq} onChange={(e) => setForm({ ...form, moq: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <input type="number" placeholder="GSM" value={form.gsm} onChange={(e) => setForm({ ...form, gsm: e.target.value })} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson" />
              <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} className="w-full px-3 py-2 rounded border border-rich-creme text-sm focus:outline-none focus:border-crimson resize-none" />
              <div className="flex gap-2 justify-end mt-4">
                <Button variant="outline" size="sm" type="button" onClick={() => setShowModal(false)}>Cancel</Button>
                <Button size="sm" type="submit" disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
