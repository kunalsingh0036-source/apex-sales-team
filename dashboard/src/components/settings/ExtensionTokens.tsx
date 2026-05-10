"use client";

import { useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";

type Token = {
  id: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export default function ExtensionTokens() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [justCreated, setJustCreated] = useState<{ label: string; token: string } | null>(null);
  const { toast } = useToast();

  async function load() {
    try {
      const data = await api.extension.listTokens();
      setTokens(data.tokens);
    } catch (err: any) {
      toast(err?.message || "Failed to load tokens", "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newLabel.trim()) {
      toast("Label is required", "error");
      return;
    }
    setCreating(true);
    try {
      const result = await api.extension.createToken(newLabel.trim());
      setJustCreated({ label: result.label, token: result.token });
      setNewLabel("");
      await load();
    } catch (err: any) {
      toast(err?.message || "Failed to create token", "error");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(token: Token) {
    if (!confirm(`Revoke token "${token.label}"? Any browser using it will stop working immediately.`)) return;
    try {
      await api.extension.revokeToken(token.id);
      toast(`Revoked: ${token.label}`, "success");
      await load();
    } catch (err: any) {
      toast(err?.message || "Failed to revoke", "error");
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(
      () => toast("Token copied to clipboard", "success"),
      () => toast("Copy failed — select and copy manually", "error")
    );
  }

  const fmt = (s: string | null) => (s ? new Date(s).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");

  return (
    <div className="bg-white rounded-xl p-6 border border-rich-creme">
      <h3 className="font-display text-lg font-bold text-crimson-dark mb-1">
        Apex Lead Capture Extension
      </h3>
      <p className="text-sm text-mid-warm mb-4">
        Each team member installs the Chrome extension and pastes their own token.
        Tokens are revocable here at any time. The extension is the only way to
        capture leads from sites that block our server (schools.org.in, GeM tenders,
        LinkedIn).
      </p>

      <details className="mb-5 text-sm">
        <summary className="cursor-pointer text-crimson hover:text-crimson-dark font-bold">
          How to install (sideload, ~2 minutes)
        </summary>
        <ol className="mt-2 ml-6 list-decimal text-mid-warm space-y-1.5">
          <li>Clone the agent repo and navigate to <code className="font-mono bg-creme px-1">apex-outreach-agent/chrome-extension/</code> (ask Kunal for access).</li>
          <li>Open <code className="font-mono bg-creme px-1">chrome://extensions/</code> in Chrome.</li>
          <li>Toggle "Developer mode" on (top right).</li>
          <li>Click "Load unpacked" → select the <code className="font-mono bg-creme px-1">chrome-extension/</code> folder.</li>
          <li>Click the new "Apex Lead Capture" extension's options page.</li>
          <li>Paste a token from below (issue one for each team member).</li>
          <li>Visit a supported page — FHRAI, schools.org.in, GeM, LinkedIn — extension will detect leads automatically.</li>
        </ol>
        <p className="mt-2 text-mid-warm text-xs italic">Chrome Web Store publication takes 1-2 business days after first submission. Sideload until then.</p>
      </details>

      {/* Just-created token notice — shown ONCE, then dismissed */}
      {justCreated && (
        <div className="mb-5 p-4 bg-creme border border-crimson rounded-md">
          <p className="font-bold text-crimson-dark text-sm mb-2">
            Token created for "{justCreated.label}". Save it now — it won't be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 font-mono text-xs bg-white px-3 py-2 rounded border border-rich-creme break-all">
              {justCreated.token}
            </code>
            <Button size="sm" onClick={() => copyToClipboard(justCreated.token)}>
              Copy
            </Button>
            <Button size="sm" variant="outline" onClick={() => setJustCreated(null)}>
              Dismiss
            </Button>
          </div>
        </div>
      )}

      {/* Create form */}
      <form onSubmit={handleCreate} className="flex gap-2 mb-5">
        <input
          type="text"
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          placeholder='Token label (e.g. "Radhika Chrome", "Office iMac")'
          className="flex-1 px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
          disabled={creating}
        />
        <Button type="submit" disabled={creating || !newLabel.trim()}>
          {creating ? "Creating..." : "Issue token"}
        </Button>
      </form>

      {/* Token table */}
      {loading ? (
        <p className="text-sm text-mid-warm">Loading…</p>
      ) : tokens.length === 0 ? (
        <p className="text-sm text-mid-warm italic">No tokens yet. Issue one above.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rich-creme bg-creme/40">
                <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Label</th>
                <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Created</th>
                <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Last Used</th>
                <th className="text-left px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Status</th>
                <th className="text-right px-3 py-2 font-label text-[10px] tracking-[0.15em] text-mid-warm uppercase">Action</th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id} className="border-b border-rich-creme/50">
                  <td className="px-3 py-2 font-bold text-warm-charcoal">{t.label}</td>
                  <td className="px-3 py-2 text-xs text-mid-warm whitespace-nowrap">{fmt(t.created_at)}</td>
                  <td className="px-3 py-2 text-xs text-mid-warm whitespace-nowrap">
                    {t.last_used_at ? fmt(t.last_used_at) : <span className="italic">never</span>}
                  </td>
                  <td className="px-3 py-2">
                    {t.revoked_at ? (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-gray-200 text-gray-700">REVOKED</span>
                    ) : (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-green-100 text-green-900">ACTIVE</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {!t.revoked_at && (
                      <button
                        onClick={() => handleRevoke(t)}
                        className="text-xs text-red-600 hover:text-red-800"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
