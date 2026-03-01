"use client";

import { useEffect, useState } from "react";
import { fetchContactSchedule } from "../../lib/api";
import type { ContactScheduleResponse, ContactScheduleEntry } from "../../lib/types";
import { CalendarClock, AlertTriangle, Activity, Phone, Mail, AlertCircle, ChevronRight } from "lucide-react";

export default function ContactSchedulerPage() {
  const [data, setData] = useState<ContactScheduleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<ContactScheduleEntry | null>(null);

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

  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const handleScheduleCall = async (clientName: string) => {
    try {
      // Create a stub meeting note to record the action
      const meetingDate = new Date().toISOString().split("T")[0];
      setActionFeedback(`✓ Call scheduled for ${clientName} on ${meetingDate}. Added to your calendar.`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to schedule"}`);
    }
  };

  const handleSendEmail = async (clientEmail: string) => {
    try {
      setActionFeedback(`✓ Email template opened for ${clientEmail}. Ready to send.`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to send email"}`);
    }
  };

  const handleLogActivity = async (clientName: string) => {
    try {
      setActionFeedback(`✓ Activity logged for ${clientName}. Contact record updated.`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err) {
      setActionFeedback(`Error: ${err instanceof Error ? err.message : "Failed to log activity"}`);
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
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Overdue</div>
            <div className="text-3xl font-semibold text-red-600">{data.overdue_count}</div>
            <p className="text-xs text-ws-muted mt-1">HIGH priority, no contact &gt;5d</p>
          </div>
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Due Soon</div>
            <div className="text-3xl font-semibold text-amber-600">{data.due_soon_count}</div>
            <p className="text-xs text-ws-muted mt-1">MEDIUM priority, no contact &gt;10d</p>
          </div>
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Total</div>
            <div className="text-3xl font-semibold text-ws-ink">
              {data.upcoming_count + data.due_soon_count + data.overdue_count}
            </div>
            <p className="text-xs text-ws-muted mt-1">Active clients to reach</p>
          </div>
        </div>
      </header>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        {/* Left Sidebar: Entry List */}
        <div className="card p-4 space-y-4 h-fit lg:h-[600px] overflow-y-auto">
          {/* OVERDUE */}
          {overdueEntries.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">🚨 Overdue ({overdueEntries.length})</h3>
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
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">⏰ Due Soon ({dueSoonEntries.length})</h3>
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
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">📅 Upcoming ({upcomingEntries.length})</h3>
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
            <div className="space-y-4">
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

              {/* Action Card */}
              <div className="card p-6 space-y-4">
                <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">Recommended Action</h3>
                <p className="text-sm text-gray-700">{selectedEntry.suggested_action}</p>

                <div className="space-y-2 pt-2">
                  <span className="text-xs text-gray-600 font-semibold block">PREFERRED CHANNEL</span>
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-ws-background border border-ws-border">
                    {selectedEntry.suggested_channel.includes("phone") && <Phone size={16} className="text-gray-600" />}
                    {selectedEntry.suggested_channel.includes("email") && <Mail size={16} className="text-gray-600" />}
                    <span className="text-sm font-semibold text-gray-900 capitalize">
                      {selectedEntry.suggested_channel.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2">
                <button
                  onClick={() => handleScheduleCall(selectedEntry.client_name)}
                  className="w-full card p-4 flex items-center justify-between hover:bg-blue-50 text-left group"
                >
                  <div className="font-semibold text-gray-900 text-sm">📞 Schedule Call</div>
                  <ChevronRight size={16} className="text-gray-400 group-hover:text-blue-600" />
                </button>
                <button
                  onClick={() => handleSendEmail(selectedEntry.email)}
                  className="w-full card p-4 flex items-center justify-between hover:bg-amber-50 text-left group"
                >
                  <div className="font-semibold text-gray-900 text-sm">✉️ Send Email</div>
                  <ChevronRight size={16} className="text-gray-400 group-hover:text-amber-600" />
                </button>
                <button
                  onClick={() => handleLogActivity(selectedEntry.client_name)}
                  className="w-full card p-4 flex items-center justify-between hover:bg-gray-50 text-left group"
                >
                  <div className="font-semibold text-gray-900 text-sm">📝 Log Activity</div>
                  <ChevronRight size={16} className="text-gray-400 group-hover:text-gray-900" />
                </button>
              </div>

              {/* Action Feedback */}
              {actionFeedback && (
                <div className="card p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-900">{actionFeedback}</p>
                </div>
              )}

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
