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
  extra_data?: { last_error?: string | null; attachments?: { filename: string; size: number; content_type: string }[] };
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
    status: "content_review",
    emailIssue: "",
  });
  const [approving, setApproving] = useState(false);
  const [approvingAll, setApprovingAll] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState<MessageItem | null>(null);
  const [suggestedReply, setSuggestedReply] = useState<string | null>(null);
  const [loadingReply, setLoadingReply] = useState(false);
  const [showComposeModal, setShowComposeModal] = useState(false);
  const [composing, setComposing] = useState(false);
  const [composeForm, setComposeForm] = useState({ lead_id: "", lead_name: "", subject: "", body: "", channel: "email" });
  const [leadSearch, setLeadSearch] = useState("");
  const [leadResults, setLeadResults] = useState<{ id: string; name: string; email: string }[]>([]);
  const [showLeadDropdown, setShowLeadDropdown] = useState(false);
  const [searchingLeads, setSearchingLeads] = useState(false);
  const { toast } = useToast();
  const [generating, setGenerating] = useState(false);

  async function fetchMessages() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filter.status) params.status = filter.status;
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
  }, [filter.status, filter.direction, filter.channel, filter.classification]);

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
    if (!composeForm.lead_id) {
      toast("Please select a lead", "error");
      return;
    }
    setComposing(true);
    try {
      await api.messages.send({
        lead_id: composeForm.lead_id,
        subject: composeForm.subject,
        body: composeForm.body,
        channel: composeForm.channel,
      });
      setShowComposeModal(false);
      setComposeForm({ lead_id: "", lead_name: "", subject: "", body: "", channel: "email" });
      setLeadSearch("");
      setLeadResults([]);
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setComposing(false);
    }
  }

  // Debounced lead search
  useEffect(() => {
    if (!leadSearch || leadSearch.length < 2) {
      setLeadResults([]);
      setShowLeadDropdown(false);
      return;
    }
    const timer = setTimeout(async () => {
      setSearchingLeads(true);
      try {
        const data = await api.leads.list({ search: leadSearch });
        const results = (data.items || []).map((l: any) => ({
          id: l.id,
          name: l.company_name || l.contact_name || l.id,
          email: l.email || "",
        }));
        setLeadResults(results);
        setShowLeadDropdown(results.length > 0);
      } catch {
        setLeadResults([]);
      } finally {
        setSearchingLeads(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [leadSearch]);

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

  async function handleApprove(id: string, scheduleAt?: string) {
    setApproving(true);
    try {
      const body = scheduleAt ? { schedule_at: scheduleAt } : undefined;
      const result = await api.messages.approve(id, body);
      if (result.status === "scheduled") {
        toast(`Scheduled for ${new Date(result.scheduled_at).toLocaleString("en-IN")}.`, "success");
      } else {
        toast("Message approved and sent.", "success");
      }
      setSelectedMessage(null);
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setApproving(false);
    }
  }

  async function handleReject(id: string) {
    try {
      await api.messages.reject(id);
      toast("Message rejected.", "info");
      setSelectedMessage(null);
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleRegenerate(id: string) {
    try {
      const result = await api.messages.regenerate(id);
      toast("Message regenerated.", "success");
      // Update the selected message with new content
      if (selectedMessage && selectedMessage.id === id) {
        setSelectedMessage({
          ...selectedMessage,
          subject: result.subject || selectedMessage.subject,
          body: result.body || selectedMessage.body,
        });
      }
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  // Edit message
  const [editing, setEditing] = useState(false);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");

  function startEdit(msg: MessageItem) {
    setEditSubject(msg.subject || "");
    setEditBody(msg.body);
    setEditing(true);
  }

  async function handleSaveEdit(id: string) {
    try {
      await api.messages.update(id, { subject: editSubject, body: editBody });
      toast("Message updated.", "success");
      setEditing(false);
      if (selectedMessage && selectedMessage.id === id) {
        setSelectedMessage({ ...selectedMessage, subject: editSubject, body: editBody });
      }
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleFileUpload(msgId: string, files: FileList | null) {
    if (!files || files.length === 0) return;
    try {
      const result = await api.messages.uploadAttachments(msgId, Array.from(files));
      toast(`${files.length} file(s) attached.`, "success");
      if (selectedMessage && selectedMessage.id === msgId) {
        setSelectedMessage({
          ...selectedMessage,
          extra_data: { ...selectedMessage.extra_data, attachments: result.attachments },
        });
      }
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleRemoveAttachment(msgId: string, filename: string) {
    try {
      await api.messages.removeAttachment(msgId, filename);
      toast("Attachment removed.", "info");
      if (selectedMessage && selectedMessage.id === msgId) {
        const atts = (selectedMessage.extra_data?.attachments || []).filter((a) => a.filename !== filename);
        setSelectedMessage({ ...selectedMessage, extra_data: { ...selectedMessage.extra_data, attachments: atts } });
      }
    } catch (err: any) {
      toast(err.message, "error");
    }
  }

  async function handleApproveAll() {
    const reviewIds = filteredMessages.filter((m) => m.status === "content_review" && !m.extra_data?.last_error).map((m) => m.id);
    if (reviewIds.length === 0) return;
    setApprovingAll(true);
    try {
      const result = await api.messages.approveBatch(reviewIds);
      toast(`Approved ${result.approved || reviewIds.length} messages.`, "success");
      fetchMessages();
    } catch (err: any) {
      toast(err.message, "error");
    } finally {
      setApprovingAll(false);
    }
  }

  const filteredMessages = messages.filter((m) => {
    if (filter.emailIssue === "ready") return !m.extra_data?.last_error;
    if (filter.emailIssue === "has_issue") return !!m.extra_data?.last_error;
    return true;
  });
  const reviewCount = filteredMessages.filter((m) => m.status === "content_review").length;

  return (
    <div>
      <Header title="Unified Inbox" />

      {/* Actions */}
      <div className="flex flex-wrap gap-2 mb-6 items-center">
        <Button size="sm" onClick={() => setShowComposeModal(true)}>Compose</Button>
        <Button variant="outline" size="sm" onClick={handleGenerateMessages} disabled={generating}>
          {generating ? "Running..." : "Generate Messages"}
        </Button>
        {reviewCount > 0 && (
          <Button size="sm" variant="primary" onClick={handleApproveAll} disabled={approvingAll}>
            {approvingAll ? "Approving..." : `Approve All (${reviewCount})`}
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-3 md:gap-4 mb-6 md:mb-8 flex-wrap">
        <select
          value={filter.status}
          onChange={(e) => setFilter({ ...filter, status: e.target.value })}
          className="px-3 py-2 border border-rich-creme rounded text-sm"
        >
          <option value="content_review">Pending Review</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
          <option value="">All Statuses</option>
        </select>
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
        <select
          value={filter.emailIssue || ""}
          onChange={(e) => setFilter({ ...filter, emailIssue: e.target.value })}
          className="px-3 py-2 border border-rich-creme rounded text-sm"
        >
          <option value="">All Messages</option>
          <option value="ready">Ready to Send</option>
          <option value="has_issue">Has Issues</option>
        </select>
        <p className="text-sm text-mid-warm self-center ml-auto">
          {loading ? "Loading..." : `${filteredMessages.length} messages`}
        </p>
      </div>

      {/* Messages list */}
      {!loading && filteredMessages.length === 0 && (
        <div className="bg-white rounded-xl p-12 text-center border border-rich-creme">
          <p className="font-display text-xl text-crimson-dark mb-2">No messages yet</p>
          <p className="text-mid-warm text-sm">
            Messages will appear here as campaigns send outreach and leads reply.
          </p>
        </div>
      )}

      {!loading && messages.length > 0 && (
        <div className="space-y-3">
          {filteredMessages.map((msg) => (
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
          <div className="w-full max-w-md rounded-none md:rounded-xl bg-white p-4 md:p-6 shadow-xl min-h-screen md:min-h-0">
            <h2 className="text-lg font-bold mb-4">Compose Message</h2>
            <form onSubmit={handleCompose} className="space-y-3">
              <div className="relative">
                {composeForm.lead_id ? (
                  <div className="flex items-center gap-2 w-full rounded border px-3 py-2 text-sm bg-creme/30">
                    <span className="font-bold text-warm-charcoal">{composeForm.lead_name}</span>
                    <button
                      type="button"
                      onClick={() => {
                        setComposeForm({ ...composeForm, lead_id: "", lead_name: "" });
                        setLeadSearch("");
                      }}
                      className="ml-auto text-mid-warm hover:text-crimson text-xs"
                    >
                      &times; Change
                    </button>
                  </div>
                ) : (
                  <input
                    type="text"
                    placeholder="Search for a lead..."
                    value={leadSearch}
                    onChange={(e) => setLeadSearch(e.target.value)}
                    className="w-full rounded border px-3 py-2 text-sm"
                    autoComplete="off"
                  />
                )}
                {showLeadDropdown && !composeForm.lead_id && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-rich-creme rounded shadow-lg max-h-48 overflow-y-auto">
                    {leadResults.map((lead) => (
                      <button
                        key={lead.id}
                        type="button"
                        className="w-full text-left px-3 py-2 text-sm hover:bg-creme/50 transition-colors"
                        onClick={() => {
                          setComposeForm({ ...composeForm, lead_id: lead.id, lead_name: lead.name });
                          setShowLeadDropdown(false);
                          setLeadSearch("");
                        }}
                      >
                        <span className="font-bold text-warm-charcoal">{lead.name}</span>
                        {lead.email && <span className="text-mid-warm ml-2">{lead.email}</span>}
                      </button>
                    ))}
                  </div>
                )}
                {searchingLeads && (
                  <p className="text-xs text-mid-warm mt-1">Searching...</p>
                )}
              </div>
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
        <div className="fixed inset-0 md:inset-y-0 md:right-0 md:left-auto w-full md:w-[520px] md:max-w-[60vw] bg-white shadow-xl border-l border-rich-creme z-50 overflow-y-auto">
          <div className="p-8">
            <button onClick={() => { setSelectedMessage(null); setSuggestedReply(null); }} className="md:hidden text-sm text-crimson mb-4">&larr; Back to messages</button>
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

            {editing ? (
              <div className="mb-4 space-y-3">
                <div>
                  <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-1">Subject</p>
                  <input
                    type="text"
                    value={editSubject}
                    onChange={(e) => setEditSubject(e.target.value)}
                    className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
                  />
                </div>
                <div>
                  <p className="font-label text-xs tracking-wider text-mid-warm uppercase mb-1">Body</p>
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    rows={12}
                    className="w-full px-3 py-2 border border-rich-creme rounded text-sm focus:outline-none focus:border-crimson"
                  />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => handleSaveEdit(selectedMessage.id)}>Save</Button>
                  <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
                </div>
              </div>
            ) : (
              <>
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
              </>
            )}

            {/* Attachments */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <p className="font-label text-xs tracking-wider text-mid-warm uppercase">Attachments</p>
                {(selectedMessage.status === "content_review" || selectedMessage.status === "draft") && (
                  <label className="text-xs text-crimson font-bold cursor-pointer hover:text-crimson-dark">
                    + Add File
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.png,.jpg,.jpeg,.gif,.webp"
                      className="hidden"
                      onChange={(e) => handleFileUpload(selectedMessage.id, e.target.files)}
                    />
                  </label>
                )}
              </div>
              {(selectedMessage.extra_data?.attachments || []).length > 0 ? (
                <div className="space-y-2">
                  {selectedMessage.extra_data!.attachments!.map((att) => (
                    <div key={att.filename} className="flex items-center justify-between bg-creme/50 rounded px-3 py-2 text-sm">
                      <div>
                        <span className="font-bold text-warm-charcoal">{att.filename}</span>
                        <span className="text-xs text-mid-warm ml-2">{(att.size / 1024).toFixed(0)} KB</span>
                      </div>
                      {(selectedMessage.status === "content_review" || selectedMessage.status === "draft") && (
                        <button
                          onClick={() => handleRemoveAttachment(selectedMessage.id, att.filename)}
                          className="text-xs text-red-600 hover:text-red-800"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-mid-warm">No attachments</p>
              )}
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

            {/* Error reason */}
            {selectedMessage.extra_data?.last_error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
                <span className="font-bold">Issue: </span>{selectedMessage.extra_data.last_error}
              </div>
            )}

            {/* Approve / Schedule / Reject / Regenerate for content_review */}
            {(selectedMessage.status === "content_review" || selectedMessage.status === "failed") && (
              <div className="mb-6 space-y-3">
                <div className="flex flex-col md:flex-row gap-2">
                  <Button size="sm" onClick={() => handleApprove(selectedMessage.id)} disabled={approving}>
                    {approving ? "Sending..." : "Send Now"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => {
                    const tomorrow9am = new Date();
                    tomorrow9am.setDate(tomorrow9am.getDate() + 1);
                    tomorrow9am.setHours(9, 0, 0, 0);
                    handleApprove(selectedMessage.id, tomorrow9am.toISOString());
                  }} disabled={approving}>
                    Tomorrow 9 AM
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => {
                    const in2h = new Date(Date.now() + 2 * 60 * 60 * 1000);
                    handleApprove(selectedMessage.id, in2h.toISOString());
                  }} disabled={approving}>
                    In 2 Hours
                  </Button>
                </div>
                <div className="flex gap-2 items-center">
                  <input
                    type="datetime-local"
                    className="px-3 py-1.5 border border-rich-creme rounded text-sm"
                    onChange={(e) => {
                      if (e.target.value) {
                        handleApprove(selectedMessage.id, new Date(e.target.value).toISOString());
                      }
                    }}
                  />
                  <span className="text-xs text-mid-warm">Pick a date and time</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => startEdit(selectedMessage)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleRegenerate(selectedMessage.id)}>
                    Regenerate
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => handleReject(selectedMessage.id)}>
                    Reject
                  </Button>
                </div>
              </div>
            )}

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
