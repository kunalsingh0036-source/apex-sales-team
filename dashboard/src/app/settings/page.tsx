"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import { api } from "@/lib/api-client";

export default function SettingsPage() {
  const [config, setConfig] = useState<any>(null);
  const [rateLimits, setRateLimits] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const configReq = fetch("/api/v1/settings/info/config").then((r) => r.ok ? r.json() : null);
        const rateReq = fetch("/api/v1/settings/info/rate-limits").then((r) => r.ok ? r.json() : null);
        const [configData, rateData] = await Promise.all([configReq, rateReq]);
        setConfig(configData);
        setRateLimits(rateData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div>
      <Header title="Settings" />

      <div className="space-y-6 max-w-4xl">
        {/* Integration Status */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Integration Status
          </h3>
          {config?.integrations ? (
            <div className="grid grid-cols-3 gap-4">
              {Object.entries(config.integrations).map(([name, connected]) => (
                <div
                  key={name}
                  className="flex items-center justify-between p-3 bg-creme/50 rounded"
                >
                  <span className="text-sm text-warm-charcoal capitalize">{name}</span>
                  <Badge variant={connected ? "success" : "default"}>
                    {connected ? "Connected" : "Not Set"}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-mid-warm">
              {loading ? "Loading..." : "Configure API keys in the .env file."}
            </p>
          )}
          <p className="text-xs text-mid-warm mt-3">
            All API keys are configured via the .env file. Changes require server restart.
          </p>
        </div>

        {/* Rate Limits */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Daily Rate Limits
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {config?.rate_limits ? (
              Object.entries(config.rate_limits).map(([channel, limit]) => (
                <div
                  key={channel}
                  className="flex justify-between items-center p-3 bg-creme/50 rounded"
                >
                  <span className="text-sm text-warm-charcoal capitalize">{channel}</span>
                  <div className="text-right">
                    <span className="font-display font-bold text-crimson-dark text-sm">
                      {rateLimits?.[channel]?.remaining ?? "..."} / {String(limit)}
                    </span>
                    <p className="text-[10px] text-mid-warm">remaining today</p>
                  </div>
                </div>
              ))
            ) : (
              [
                { label: "Email", value: "200/day" },
                { label: "LinkedIn", value: "25/day" },
                { label: "WhatsApp", value: "100/day" },
                { label: "Instagram", value: "50/day" },
              ].map((item) => (
                <div
                  key={item.label}
                  className="flex justify-between items-center p-3 bg-creme/50 rounded"
                >
                  <span className="text-sm text-warm-charcoal">{item.label}</span>
                  <span className="font-display font-bold text-crimson-dark text-sm">
                    {item.value}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Sender Info */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Sender Configuration
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-creme/50 rounded">
              <span className="text-sm text-mid-warm">Sender Email</span>
              <span className="text-sm font-mono text-warm-charcoal">
                {config?.sender_email || "brand@apexhumancompany.com"}
              </span>
            </div>
          </div>
        </div>

        {/* Brand Voice */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Brand Voice
          </h3>
          <p className="text-sm text-mid-warm mb-4">
            The Apex Human Company brand voice is pre-configured based on the
            official brand guidelines. All AI-generated messages follow the
            authoritative, transparent, confident, and warm tone.
          </p>
          <div className="bg-creme/50 p-4 rounded mb-4">
            <p className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-2">
              Active Voice Traits
            </p>
            <div className="flex flex-wrap gap-2">
              {["Authoritative", "Transparent", "Confident", "Warm", "Factory-Direct", "No Middlemen", "Premium Quality"].map(
                (trait) => (
                  <span
                    key={trait}
                    className="px-3 py-1 bg-crimson text-creme text-xs rounded-full font-bold"
                  >
                    {trait}
                  </span>
                )
              )}
            </div>
          </div>
          <div className="bg-creme/50 p-4 rounded">
            <p className="font-label text-xs tracking-[0.15em] text-mid-warm uppercase mb-2">
              Industry-Specific Overrides
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                "Technology & SaaS", "Banking & Finance", "Defence & Government",
                "Hospitality", "Healthcare", "Real Estate", "Education",
                "Events", "FMCG",
              ].map((industry) => (
                <span
                  key={industry}
                  className="px-3 py-1 bg-rich-creme text-warm-charcoal text-xs rounded font-bold"
                >
                  {industry}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Sequence Timing */}
        <div className="bg-white rounded-xl p-6 border border-rich-creme">
          <h3 className="font-display text-lg font-bold text-crimson-dark mb-4">
            Send Window & Timing
          </h3>
          <div className="space-y-2 text-sm text-warm-charcoal">
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Optimal Send Window</span>
              <span className="font-bold">10:00 AM - 11:30 AM IST</span>
            </div>
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Cross-Channel Cooldown</span>
              <span className="font-bold">48 hours minimum</span>
            </div>
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Max Channels / Lead / Week</span>
              <span className="font-bold">2 channels</span>
            </div>
            <div className="flex justify-between p-3 bg-creme/50 rounded">
              <span className="text-mid-warm">Timezone</span>
              <span className="font-bold">Asia/Kolkata (IST)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
