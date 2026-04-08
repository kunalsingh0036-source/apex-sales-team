"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/ui/Toast";

interface MessageItem {
  id: string;
  lead_id: string;
  channel: string;
  direction: string;
  subject: string | null;
  body: string;
  status: string;
  classification: string | null;
  ai_suggested_reply: string | null;
  sent_at: string | null;
  created_at: string;
}

const CLASSIFICATION_COLORS: Record<string, "success" | "crimson" | "warning" | "info" | "default"> = {
  interested: "success",
  meeting_request: "success",
  requesting_info: "info",
  not_interested: "crimson",
  wrong_person: "warning",
  ooo: "default",
  unsubscribe: "crimson",
};

export default function MessagesPage() {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    direction: "",
    channel: "",
    classification: "",
  });
  const [selectedMessage, setSelectedMessage] = useState<MessageItem | null>(null);
  const [suggestedReply, setSuggestedReply] = useState<string | null>(null);
  const [loadingReply, setLoadingReply] = useState(false);
  const [showComposeModal, setShowComposeModal] = useState(false);
  const [composing, setComposing] = useState(false);
  const [composeForm, setComposeForm] = useState({ to: "", subject: "", body: "", channel: "email" });
  const { toast } = useToast();
  const [generating, setGenerating] = useState(false);

  async function fetchMessages() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filter.direction) params.direction = filter.direction;
      if (filter.channel) params.channel = filter.channel;
      if (filter.classification) params.classification = filter.classification;
      const data = await api.messages.list(params);
      setMessages(data.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchMessages();
  }, [filter.direction, filter.channel, filter.classification]);

  async function handleSuggestReply(msg: MessageItem) {
    setSelectedMessage(msg);
    setSuggestedReply(null);
    setLoadingReply(true);
    try {
      const data = await api.messages.suggestReply(msg.id);
      setSuggestedReply(data.suggested_reply);
    } catch (err) {
      console.error(err);
      setSuggestedReply("Failed to generate reply.");
    } finally {
      setLoadingReply(false);
    }
  }

  async function handleClassify(msgId: string, classification: string) {
    try {
      await api.messages.classify(msgId, classification);
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleCompose(e: React.FormEvent) {
    e.preventDefault();
    setComposing(true);
    try {
      await api.messages.send(composeForm);
      setShowComposeModal(false);
      setComposeForm({ to: "", subject: "", body: "", channel: "email" });
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setComposing(false);
    }
  }

  async function handleGenerateMessages() {
    setGenerating(true);
    try {
      const result = await api.autopilot.trigger("advance");
      toast("Advancing enrollments. Messages will appear in the review queue.", "success");
      setTimeout(() => fetchMessages(), 5000);
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div>
      <Header title="Unified Inbox" />

      {/* Actions */}
      <div className="flex gap-2 mb-6">
        <Button size="sm" onClick={() => setShowComposeModal(true)}>Compose</Button>
        <Button variant="outline" size="sm" onClick={handleGenerateMessages} disabled={generating}>
          {generating ? "Running..." : "Generate Messages"}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-8 flex-wrap">
        <select
          value={filter.direction}
          onChange={(e) => setFilter({ ...filter, direction: e.target.value })}
          className="px-3 py-2 border border-rich-creme rounded text-sm"
        >
          <option value="">All Directions</option>
          <option value="inbound">Inbound</option>
          <option value="outbound">Outbound</option>
        </select>
        <select
          value={filter.channel}
          onChange={(e) => setFilter({ ...filter, channel: e.target.value })}
          className="px-3 py-2 border border-rich-creme rounded text-sm"
        >
          <option value="">All Channels</option>
          <option value="email">Email</option>
          <option value="linkedin">LinkedIn</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="instagram">Instagram</option>
        </select>
        <select
          value={filter.classification}
          onChange={(e) => setFilter({ ...filter, classification: e.target.value })}
          className="px-3 py-2 border border-rich-creme rounded text-sm"
        >
          <option value="">All Classifications</option>
          <option value="interested">Interested</option>
          <option value="meeting_request">Meeting Request</option>
          <option value="requesting_info">Requesting Info</option>
          <option value="not_interested">Not Interested</option>
          <option value="wrong_person">Wrong Person</option>
          <option value="ooo">Out of Office</option>
          <option value="unsubscribe">Unsubscribe</option>
        </select>
        <p className="text-sm text-mid-warm self-center ml-auto">
          {loading ? "Loading..." : `${messages.length} messages`}
        </p>
      </div>

      {/* Messages list */}
      {!loading && messages.length === 0 && (
        <div className="bg-white rounded-xl p-12 text-center border border-rich-creme">
          <p className="font-display text-xl text-crimson-dark mb-2">No messages yet</p>
          <p className="text-mid-warm text-sm">
            Messages will appear here as campaigns send outreach and leads reply.
          </p>
        </div>
      )}

      {!loading && messages.length > 0 && (
        <div className="space-y-3">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`bg-white rounded-xl p-6 border cursor-pointer transition-colors ${
                selectedMessage?.id === msg.id
                  ? "border-crimson"
                  : "border-rich-creme hover:border-crimson/40"
              }`}
              onClick={() => setSelectedMessage(msg)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Badge variant={msg.direction === "inbound" ? "info" : "default"}>
                    {msg.direction === "inbound" ? "IN" : "OUT"}
                  </Badge>
                  <Badge variant="crimson">{msg.channel}</Badge>
                  {msg.classification && (
                    <Badge variant={CLASSIFICATION_COLORS[msg.classification] || "default"}>
                      {msg.classification.replace(/_/g, " ")}
                    </Badge>
                  )}
                  <Badge variant={msg.status === "sent" ? "success" : msg.status === "failed" ? "crimson" : "default"}>
                    {msg.status}
                  </Badge>
                </div>
                <span className="text-xs text-mid-warm">
                  {msg.sent_at
                    ? new Date(msg.sent_at).toLocaleString("en-IN")
                    : new Date(msg.created_at).toLocaleString("en-IN")}
                </span>
              </div>

              {msg.subject && (
                <p className="font-bold text-sm text-warm-charcoal mb-1 truncate">{msg.subject}</p>
              )}
              <p className="text-sm text-mid-warm line-clamp-2">{msg.body}</p>

              <div className="text-xs text-mid-warm mt-2">
                Lead: {msg.lead_id.substring(0, 8)}...
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Compose Modal */}
      {showComposeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold mb-4">Compose Message</h2>
            <form onSubmit={handleCompose} className="space-y-3">
              <input
                type="email"
                placeholder="To (email)"
                value={composeForm.to}
                onChange={(e) => setComposeForm({ ...composeForm, to: e.target.value })}
                required
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <input
                type="text"
                placeholder="Subject"
                value={composeForm.subject}
                onChange={(e) => setComposeForm({ ...composeForm, subject: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <textarea
                placeholder="Body"
                value={composeForm.body}
                onChange={(e) => setComposeForm({ ...composeForm, body: e.target.value })}
                required
                rows={5}
                className="w-full rounded border px-3 py-2 text-sm"
              />
              <select
                value={composeForm.channel}
                onChange={(e) => setComposeForm({ ...composeForm, channel: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
              >
                <option value="email">Email</option>
                <option value="linkedin">LinkedIn</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="instagram">Instagram</option>
              </select>
              <div className="flex gap-2 justify-end mt-4">
                <Button variant="outline" size="sm" type="button" onClick={() => setShowComposeModal(false)}>Cancel</Button>
                <Button size="sm" type="submit" disabled={composing}>{composing ? "Sending..." : "Send"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Detail panel */}
      {selectedMessage && (
        <div className="fixed inset-y-0 right-0 w-[520px] max-w-[60vw] bg-white shadow-xl border-l border-rich-creme z-50 overflow-y-auto">
          <div className="p-8">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-display text-lg font-bold text-crimson-dark">Message Detail</h3>
              <button
                onClick={() => { setSelectedMessage(null); setSuggestedReply(null); }}
                className="text-mid-warm hover:text-crimson text-xl"
              >
                &times;
              </button>
            </div>

            <div className="flex items-center gap-2 mb-4">
              <Badge variant={selectedMessage.direction === "inbound" ? "info" : "default"}>
                {selectedMessage.direction}
              </Badge>
              <Badge variant="crimson">{selectedMessage.channel}</Badge>
              <Badge variant={selectedMessage.status === "sent" ? "success" : selectedMessage.status === "failed" ? "crimson" : "default"}>
                {selectedMessage.status}
              </Badge>
            </div>

            {selectedMessage.subject && (
              <div className="mb-4">
                <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-1">Subject</p>
                <p className="text-sm font-bold text-warm-charcoal">{selectedMessage.subject}</p>
              </div>
            )}

            <div className="mb-4">
              <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-1">Body</p>
              <div className="bg-creme/50 rounded p-4 text-sm text-warm-charcoal whitespace-pre-wrap">
                {selectedMessage.body}
              </div>
            </div>

            <div className="mb-4">
              <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-1">Lead ID</p>
              <p className="text-sm font-mono text-warm-charcoal">{selectedMessage.lead_id}</p>
            </div>

            <div className="mb-4">
              <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-1">Timestamp</p>
              <p className="text-sm text-warm-charcoal">
                {selectedMessage.sent_at
                  ? new Date(selectedMessage.sent_at).toLocaleString("en-IN")
                  : new Date(selectedMessage.created_at).toLocaleString("en-IN")}
              </p>
            </div>

            {/* Classification controls for inbound */}
            {selectedMessage.direction === "inbound" && (
              <div className="mb-6">
                <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-2">Classification</p>
                {selectedMessage.classification && (
                  <Badge
                    variant={CLASSIFICATION_COLORS[selectedMessage.classification] || "default"}
                  >
                    {selectedMessage.classification.replace(/_/g, " ")}
                  </Badge>
                )}
                <div className="flex flex-wrap gap-2 mt-2">
                  {["interested", "meeting_request", "requesting_info", "not_interested", "wrong_person", "ooo"].map((cls) => (
                    <button
                      key={cls}
                      onClick={() => handleClassify(selectedMessage.id, cls)}
                      className={`text-xs px-2 py-1 rounded border transition-colors ${
                        selectedMessage.classification === cls
                          ? "bg-crimson text-white border-crimson"
                          : "border-rich-creme text-mid-warm hover:border-crimson hover:text-crimson"
                      }`}
                    >
                      {cls.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* AI suggested reply */}
            {selectedMessage.direction === "inbound" && (
              <div className="border-t border-rich-creme pt-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="font-label text-xs tracking-wider text-mid-warm uppercase">AI Suggested Reply</p>
                  <Button
                    size="sm"
                    onClick={() => handleSuggestReply(selectedMessage)}
                    disabled={loadingReply}
                  >
                    {loadingReply ? "Generating..." : "Generate Reply"}
                  </Button>
                </div>

                {selectedMessage.ai_suggested_reply && !suggestedReply && (
                  <div className="bg-creme/50 rounded p-4 text-sm text-warm-charcoal whitespace-pre-wrap">
                    {selectedMessage.ai_suggested_reply}
                  </div>
                )}

                {suggestedReply && (
                  <div className="bg-creme/50 rounded p-4 text-sm text-warm-charcoal whitespace-pre-wrap border-l-4 border-crimson">
                    {suggestedReply}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
