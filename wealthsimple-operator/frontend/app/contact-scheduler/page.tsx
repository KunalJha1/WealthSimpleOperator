"use client";

import { useEffect, useState } from "react";
import { fetchContactSchedule, generateCallScript, generateEmailDraft, approveCallScheduled, approveEmailSent, approveActivityLogged } from "../../lib/api";
import type { ContactScheduleResponse, ContactScheduleEntry } from "../../lib/types";
import {
  CalendarClock, AlertTriangle, Activity, Phone, Mail, AlertCircle, ChevronRight,
  Clock, AlertOctagon, CheckCircle2, MessageSquare, X, Copy, Zap
} from "lucide-react";

interface CallScriptDraft {
  client_id: number;
  client_name: string;
  script: string;
  key_talking_points: string[];
  provider: string;
}

interface EmailDraftType {
  client_id: number;
  client_name: string;
  subject: string;
  body: string;
  key_points: string[];
  provider: string;
}

export default function ContactSchedulerPage() {
  const [data, setData] = useState<ContactScheduleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<ContactScheduleEntry | null>(null);

  // Modal states
  const [callScriptDraft, setCallScriptDraft] = useState<CallScriptDraft | null>(null);
  const [emailDraft, setEmailDraft] = useState<EmailDraftType | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const response = await fetchContactSchedule();
        setData(response);
        if (response.entries.length > 0) {
          setSelectedEntry(response.entries[0]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load contact schedule");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  // Handle escape key and click-outside to close modals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setCallScriptDraft(null);
        setEmailDraft(null);
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("modal-backdrop")) {
        setCallScriptDraft(null);
        setEmailDraft(null);
      }
    };

    if (callScriptDraft || emailDraft) {
      document.addEventListener("keydown", handleKeyDown);
      document.addEventListener("click", handleClickOutside);
      return () => {
        document.removeEventListener("keydown", handleKeyDown);
        document.removeEventListener("click", handleClickOutside);
      };
    }
  }, [callScriptDraft, emailDraft]);

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case "OVERDUE":
        return "bg-red-50 border-l-4 border-red-500";
      case "DUE_SOON":
        return "bg-amber-50 border-l-4 border-amber-500";
      case "UPCOMING":
        return "bg-blue-50 border-l-4 border-blue-500";
      default:
        return "bg-gray-50";
    }
  };

  const getUrgencyBadgeColor = (urgency: string) => {
    switch (urgency) {
      case "OVERDUE":
        return "bg-red-100 text-red-800 font-semibold";
      case "DUE_SOON":
        return "bg-amber-100 text-amber-800 font-semibold";
      case "UPCOMING":
        return "bg-blue-100 text-blue-800 font-semibold";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "HIGH":
        return "text-red-600 font-semibold";
      case "MEDIUM":
        return "text-amber-600 font-semibold";
      case "LOW":
        return "text-emerald-600 font-semibold";
      default:
        return "text-gray-600";
    }
  };

  const handleScheduleCall = async () => {
    if (!selectedEntry) return;
    try {
      setDraftLoading(true);
      const draft = await generateCallScript(selectedEntry.client_id);
      setCallScriptDraft(draft);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to generate call script"}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } finally {
      setDraftLoading(false);
    }
  };

  const handleSendEmail = async () => {
    if (!selectedEntry) return;
    try {
      setDraftLoading(true);
      const draft = await generateEmailDraft(selectedEntry.client_id);
      setEmailDraft(draft);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to generate email"}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } finally {
      setDraftLoading(false);
    }
  };

  const handleApproveCall = async () => {
    if (!selectedEntry) return;
    try {
      setApprovalLoading(true);
      const result = await approveCallScheduled(selectedEntry.client_id);
      setCallScriptDraft(null);
      setActionFeedback(`✓ ${result.message}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to schedule call"}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleApproveEmail = async () => {
    if (!selectedEntry) return;
    try {
      setApprovalLoading(true);
      const result = await approveEmailSent(selectedEntry.client_id);
      setEmailDraft(null);
      setActionFeedback(`✓ ${result.message}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to send email"}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleLogActivity = async () => {
    if (!selectedEntry) return;
    try {
      setApprovalLoading(true);
      const result = await approveActivityLogged(selectedEntry.client_id);
      setActionFeedback(`✓ ${result.message}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to log activity"}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } finally {
      setApprovalLoading(false);
    }
  };

  if (loading) {
    return (
      <section className="space-y-5 page-enter">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <CalendarClock size={24} className="text-blue-600" />
            </div>
            <div>
              <h1 className="page-title">Contact Scheduler</h1>
              <p className="text-xs text-ws-muted font-semibold tracking-wide">CLIENT OUTREACH TIMELINE</p>
            </div>
          </div>
        </header>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <Activity className="w-8 h-8 text-ws-muted mx-auto mb-2 animate-spin" />
            <p className="text-sm text-ws-muted">Loading schedule...</p>
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="space-y-5 page-enter">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-red-50 border border-red-200">
              <AlertTriangle size={24} className="text-red-600" />
            </div>
            <div>
              <h1 className="page-title">Error</h1>
              <p className="text-xs text-ws-muted font-semibold tracking-wide">Unable to load schedule</p>
            </div>
          </div>
        </header>
        <div className="card p-6 border-red-200 bg-red-50">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="space-y-5 page-enter">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <CalendarClock size={24} className="text-blue-600" />
            </div>
            <div>
              <h1 className="page-title">Contact Scheduler</h1>
              <p className="page-subtitle">No data available</p>
            </div>
          </div>
        </header>
      </section>
    );
  }

  const overdueEntries = data.entries.filter(e => e.urgency === "OVERDUE");
  const dueSoonEntries = data.entries.filter(e => e.urgency === "DUE_SOON");
  const upcomingEntries = data.entries.filter(e => e.urgency === "UPCOMING");

  return (
    <section className="space-y-5 page-enter">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
            <CalendarClock size={24} className="text-blue-600" />
          </div>
          <div>
            <h1 className="page-title">Contact Scheduler</h1>
            <p className="text-xs text-ws-muted font-semibold tracking-wide">CLIENT OUTREACH TIMELINE</p>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-3 gap-3">
          <div className="card p-4 stat-enter stagger-1">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Overdue</div>
            <div className="text-3xl font-semibold text-red-600">{data.overdue_count}</div>
            <p className="text-xs text-ws-muted mt-1">HIGH priority, no contact &gt;5d</p>
          </div>
          <div className="card p-4 stat-enter stagger-2">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Due Soon</div>
            <div className="text-3xl font-semibold text-amber-600">{data.due_soon_count}</div>
            <p className="text-xs text-ws-muted mt-1">MEDIUM priority, no contact &gt;10d</p>
          </div>
          <div className="card p-4 stat-enter stagger-3">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Total</div>
            <div className="text-3xl font-semibold text-ws-ink">
              {data.upcoming_count + data.due_soon_count + data.overdue_count}
            </div>
            <p className="text-xs text-ws-muted mt-1">Active clients to reach</p>
          </div>
        </div>
      </header>

      {/* Intro Card */}
      <div className="card p-5 bg-blue-50 border border-blue-200 space-y-2">
        <div className="flex items-start gap-3">
          <Clock size={16} className="text-blue-600 flex-shrink-0 mt-1" />
          <div>
            <p className="text-sm font-semibold text-blue-900">Smart Outreach Management</p>
            <p className="text-xs text-blue-800 mt-1">AI identifies which clients need attention based on alert priority and days since last contact. You decide when, how, and what to communicate.</p>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        {/* Left Sidebar: Entry List */}
        <div className="card p-4 space-y-4 h-fit lg:h-[600px] overflow-y-auto">
          {/* OVERDUE */}
          {overdueEntries.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <AlertOctagon size={14} className="text-red-600" />
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Overdue ({overdueEntries.length})</h3>
              </div>
              <div className="space-y-2">
                {overdueEntries.map(entry => (
                  <button
                    key={entry.client_id}
                    onClick={() => setSelectedEntry(entry)}
                    className={`w-full text-left p-3 rounded-lg border-2 transition ${
                      selectedEntry?.client_id === entry.client_id
                        ? "border-red-500 bg-red-50"
                        : "border-ws-border bg-white hover:bg-gray-50"
                    }`}
                  >
                    <div className="font-semibold text-gray-900 text-sm">{entry.client_name}</div>
                    <div className="text-xs text-ws-muted mt-1">{entry.alert_count} alert{entry.alert_count !== 1 ? 's' : ''}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* DUE_SOON */}
          {dueSoonEntries.length > 0 && (
            <div className="space-y-2 border-t border-ws-border pt-4">
              <div className="flex items-center gap-2">
                <Clock size={14} className="text-amber-600" />
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Due Soon ({dueSoonEntries.length})</h3>
              </div>
              <div className="space-y-2">
                {dueSoonEntries.map(entry => (
                  <button
                    key={entry.client_id}
                    onClick={() => setSelectedEntry(entry)}
                    className={`w-full text-left p-3 rounded-lg border-2 transition ${
                      selectedEntry?.client_id === entry.client_id
                        ? "border-amber-500 bg-amber-50"
                        : "border-ws-border bg-white hover:bg-gray-50"
                    }`}
                  >
                    <div className="font-semibold text-gray-900 text-sm">{entry.client_name}</div>
                    <div className="text-xs text-ws-muted mt-1">{entry.alert_count} alert{entry.alert_count !== 1 ? 's' : ''}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* UPCOMING */}
          {upcomingEntries.length > 0 && (
            <div className="space-y-2 border-t border-ws-border pt-4">
              <div className="flex items-center gap-2">
                <CalendarClock size={14} className="text-blue-600" />
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Upcoming ({upcomingEntries.length})</h3>
              </div>
              <div className="space-y-2">
                {upcomingEntries.map(entry => (
                  <button
                    key={entry.client_id}
                    onClick={() => setSelectedEntry(entry)}
                    className={`w-full text-left p-3 rounded-lg border-2 transition ${
                      selectedEntry?.client_id === entry.client_id
                        ? "border-blue-500 bg-blue-50"
                        : "border-ws-border bg-white hover:bg-gray-50"
                    }`}
                  >
                    <div className="font-semibold text-gray-900 text-sm">{entry.client_name}</div>
                    <div className="text-xs text-ws-muted mt-1">{entry.alert_count} alert{entry.alert_count !== 1 ? 's' : ''}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Panel: Detail View */}
        <div>
          {selectedEntry ? (
            <div key={selectedEntry.client_id} className="space-y-4 brief-enter">
              {/* Client Card */}
              <div className={`card p-6 ${getUrgencyColor(selectedEntry.urgency)}`}>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">{selectedEntry.client_name}</h2>
                    <p className="text-sm text-gray-600 mt-1">{selectedEntry.segment}</p>
                  </div>
                  <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${getUrgencyBadgeColor(selectedEntry.urgency)}`}>
                    {selectedEntry.urgency}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-xs text-gray-600 font-semibold block mb-1">EMAIL</span>
                    <div className="font-semibold text-gray-900 break-all">{selectedEntry.email}</div>
                  </div>
                  <div>
                    <span className="text-xs text-gray-600 font-semibold block mb-1">PRIORITY</span>
                    <span className={`inline-block px-2 py-1 rounded text-xs font-semibold bg-white ${getPriorityColor(selectedEntry.highest_priority)}`}>
                      {selectedEntry.highest_priority}
                    </span>
                  </div>
                  <div>
                    <span className="text-xs text-gray-600 font-semibold block mb-1">DAYS SINCE CONTACT</span>
                    <div className="font-semibold text-gray-900">{selectedEntry.days_since_contact} days</div>
                  </div>
                  <div>
                    <span className="text-xs text-gray-600 font-semibold block mb-1">OPEN ALERTS</span>
                    <div className="font-semibold text-gray-900">{selectedEntry.alert_count}</div>
                  </div>
                </div>
              </div>

              {/* Open Alerts Context */}
              <div className="card p-6 space-y-4 border-l-4 border-l-red-500 bg-red-50">
                <div className="flex items-start gap-3">
                  <AlertTriangle size={18} className="text-red-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="text-sm font-semibold text-red-900">Open Alerts</h3>
                    <p className="text-sm text-red-800 mt-2">
                      {selectedEntry.alert_count > 0
                        ? `${selectedEntry.alert_count} active alert${selectedEntry.alert_count !== 1 ? 's' : ''} requiring review. Contact this client to discuss portfolio changes and risk mitigation.`
                        : "No active alerts—routine check-in recommended."}
                    </p>
                  </div>
                </div>

                <div className="pt-2 border-t border-red-200">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-xs text-red-700 font-semibold block mb-1">PRIORITY LEVEL</span>
                      <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${getPriorityColor(selectedEntry.highest_priority)} bg-white`}>
                        {selectedEntry.highest_priority}
                      </span>
                    </div>
                    <div>
                      <span className="text-xs text-red-700 font-semibold block mb-1">ALERT COUNT</span>
                      <span className="font-bold text-red-700 text-lg">{selectedEntry.alert_count}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recommended Action */}
              <div className="card p-6 space-y-4">
                <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">Suggested Conversation</h3>
                <p className="text-sm text-gray-700 leading-relaxed">{selectedEntry.suggested_action}</p>

                <div className="space-y-2 pt-4 border-t border-ws-border">
                  <span className="text-xs text-gray-600 font-semibold block uppercase">BEST CONTACT METHOD</span>
                  <div className="flex items-center gap-3 p-4 rounded-lg bg-blue-50 border-2 border-blue-200">
                    {selectedEntry.suggested_channel.includes("phone") && <Phone size={18} className="text-blue-600" />}
                    {selectedEntry.suggested_channel.includes("email") && <Mail size={18} className="text-blue-600" />}
                    <span className="text-sm font-semibold text-blue-900 capitalize">
                      {selectedEntry.suggested_channel.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="space-y-3">
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">AI-Powered Actions</h3>
                <div className="grid grid-cols-3 gap-3">
                  <button
                    onClick={handleScheduleCall}
                    disabled={draftLoading}
                    className="p-4 rounded-lg bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-400 text-white transition shadow-md hover:shadow-lg flex flex-col items-center justify-center gap-2"
                  >
                    <Phone size={18} />
                    <span className="text-xs font-semibold text-center">Schedule Call</span>
                  </button>
                  <button
                    onClick={handleSendEmail}
                    disabled={draftLoading}
                    className="p-4 rounded-lg bg-amber-600 hover:bg-amber-700 active:bg-amber-800 disabled:bg-gray-400 text-white transition shadow-md hover:shadow-lg flex flex-col items-center justify-center gap-2"
                  >
                    <Mail size={18} />
                    <span className="text-xs font-semibold text-center">Send Email</span>
                  </button>
                  <button
                    onClick={handleLogActivity}
                    disabled={approvalLoading}
                    className="p-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:bg-gray-400 text-white transition shadow-md hover:shadow-lg flex flex-col items-center justify-center gap-2"
                  >
                    <MessageSquare size={18} />
                    <span className="text-xs font-semibold text-center">Log Activity</span>
                  </button>
                </div>
              </div>

              {/* Call Script Modal */}
              {callScriptDraft && (
                <div className="modal-backdrop fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                  <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
                    <div className="sticky top-0 bg-blue-50 border-b border-blue-200 p-6 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Phone size={20} className="text-blue-600" />
                        <h2 className="text-lg font-semibold text-gray-900">Call Script - Review & Approve</h2>
                      </div>
                      <button
                        onClick={() => setCallScriptDraft(null)}
                        className="p-2 hover:bg-blue-100 rounded-lg transition"
                      >
                        <X size={20} className="text-gray-600" />
                      </button>
                    </div>

                    <div className="p-6 space-y-6">
                      <div>
                        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">Key Talking Points</h3>
                        <ul className="space-y-2">
                          {callScriptDraft.key_talking_points.map((point, i) => (
                            <li key={i} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                              <Zap size={16} className="text-blue-600 flex-shrink-0 mt-0.5" />
                              <span className="text-sm text-blue-900">{point}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">Call Script</h3>
                        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 text-sm text-gray-700 whitespace-pre-wrap max-h-96 overflow-y-auto font-mono">
                          {callScriptDraft.script}
                        </div>
                      </div>

                      <div className="flex gap-3 pt-4 border-t border-gray-200">
                        <button
                          onClick={() => setCallScriptDraft(null)}
                          className="flex-1 px-4 py-3 rounded-lg border-2 border-gray-300 text-gray-700 font-semibold hover:bg-gray-50 transition"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleApproveCall}
                          disabled={approvalLoading}
                          className="flex-1 px-4 py-3 rounded-lg bg-ws-green hover:opacity-90 disabled:bg-gray-400 text-white font-semibold transition flex items-center justify-center gap-2 shadow-md hover:shadow-lg"
                        >
                          <CheckCircle2 size={18} />
                          Approve & Schedule
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Email Draft Modal */}
              {emailDraft && (
                <div className="modal-backdrop fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                  <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
                    <div className="sticky top-0 bg-amber-50 border-b border-amber-200 p-6 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Mail size={20} className="text-amber-600" />
                        <h2 className="text-lg font-semibold text-gray-900">Email Draft - Review & Approve</h2>
                      </div>
                      <button
                        onClick={() => setEmailDraft(null)}
                        className="p-2 hover:bg-amber-100 rounded-lg transition"
                      >
                        <X size={20} className="text-gray-600" />
                      </button>
                    </div>

                    <div className="p-6 space-y-6">
                      <div>
                        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-2">Key Points</h3>
                        <ul className="space-y-2 mb-6">
                          {emailDraft.key_points.map((point, i) => (
                            <li key={i} className="flex items-start gap-3 p-3 bg-amber-50 rounded-lg border border-amber-200">
                              <Zap size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
                              <span className="text-sm text-amber-900">{point}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="border-t border-gray-200 pt-4">
                        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">Email Preview</h3>
                        <div className="bg-white border-2 border-gray-300 rounded-lg p-4 flex flex-col">
                          <div className="mb-4 pb-4 border-b border-gray-200">
                            <p className="text-xs text-gray-600 font-semibold mb-1">Subject:</p>
                            <p className="text-sm font-semibold text-gray-900">{emailDraft.subject}</p>
                          </div>
                          <div className="text-sm text-gray-700 whitespace-pre-wrap flex-1">
                            {emailDraft.body}
                          </div>
                          <div className="mt-6 pt-4 border-t border-gray-200 text-xs text-gray-600">
                            <p className="font-semibold mb-2">Wealthsimple</p>
                            <p>Best regards,</p>
                            <p>Your Financial Advisor</p>
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-3 pt-4 border-t border-gray-200">
                        <button
                          onClick={() => setEmailDraft(null)}
                          className="flex-1 px-4 py-3 rounded-lg border-2 border-gray-300 text-gray-700 font-semibold hover:bg-gray-50 transition"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleApproveEmail}
                          disabled={approvalLoading}
                          className="flex-1 px-4 py-3 rounded-lg bg-ws-green hover:opacity-90 disabled:bg-gray-400 text-white font-semibold transition flex items-center justify-center gap-2 shadow-md hover:shadow-lg"
                        >
                          <CheckCircle2 size={18} />
                          Approve & Send
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Action Feedback */}
              {actionFeedback && (
                <div className="card p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-900">{actionFeedback}</p>
                </div>
              )}

              {/* Additional Tools Section */}
              <div className="border-t border-gray-200 pt-6 space-y-4">
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Additional Tools</h3>

                {/* Rebalancing */}
                <div className="card p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-gray-900">Auto-Reallocation</h4>
                      <p className="text-xs text-gray-600 mt-1">Generate allocation adjustment plan with risk metrics</p>
                    </div>
                    <Zap size={16} className="text-blue-600 flex-shrink-0" />
                  </div>
                  <button className="w-full px-4 py-2 rounded-lg bg-blue-100 hover:bg-blue-200 text-blue-700 font-semibold transition text-sm">
                    Analyze & Rebalance
                  </button>
                </div>

                {/* Simulation */}
                <div className="card p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-gray-900">Scenario Simulator</h4>
                      <p className="text-xs text-gray-600 mt-1">Run market scenarios and generate action playbooks</p>
                    </div>
                    <Zap size={16} className="text-amber-600 flex-shrink-0" />
                  </div>
                  <button className="w-full px-4 py-2 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-700 font-semibold transition text-sm">
                    Run Simulations
                  </button>
                </div>

                {/* Risk Dashboard */}
                <div className="card p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-gray-900">Risk Dashboard</h4>
                      <p className="text-xs text-gray-600 mt-1">View detailed portfolio risk metrics and drift analysis</p>
                    </div>
                    <AlertTriangle size={16} className="text-red-600 flex-shrink-0" />
                  </div>
                  <button className="w-full px-4 py-2 rounded-lg bg-red-100 hover:bg-red-200 text-red-700 font-semibold transition text-sm">
                    View Risk Metrics
                  </button>
                </div>

                {/* Tax Loss Harvesting */}
                <div className="card p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-gray-900">Tax-Loss Harvesting</h4>
                      <p className="text-xs text-gray-600 mt-1">Identify and execute tax optimization opportunities</p>
                    </div>
                    <Zap size={16} className="text-emerald-600 flex-shrink-0" />
                  </div>
                  <button className="w-full px-4 py-2 rounded-lg bg-emerald-100 hover:bg-emerald-200 text-emerald-700 font-semibold transition text-sm">
                    Find Opportunities
                  </button>
                </div>
              </div>

              {/* AI Boundary */}
              <div className="card p-4 bg-blue-50 border-blue-200">
                <p className="text-xs text-blue-900 leading-relaxed">
                  <strong>AI identifies who needs contact.</strong> You decide timing, channel, and approach.
                </p>
              </div>
            </div>
          ) : (
            <div className="card p-12 flex items-center justify-center h-96">
              <div className="text-center">
                <AlertCircle className="w-8 h-8 text-ws-muted mx-auto mb-2" />
                <p className="text-sm text-ws-muted">Select a client to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
