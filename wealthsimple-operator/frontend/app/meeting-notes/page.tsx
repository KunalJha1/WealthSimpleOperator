"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "../../components/Buttons";
import {
  fetchMonitoringSummary,
  fetchMeetingNotes,
  createMeetingNote,
  summarizeTranscript,
  updateActionItem,
  fetchPreCallBrief
} from "../../lib/api";
import type {
  MonitoringUniverseSummary,
  MonitoringClientRow,
  MeetingNote,
  MeetingNoteCreate,
  MeetingNoteType,
  PreCallBriefResponse
} from "../../lib/types";
import { ChevronDown, ChevronUp, FileText, CheckCircle2, AlertCircle, Search, X } from "lucide-react";

export default function MeetingNotesPage() {
  const searchParams = useSearchParams();
  const portfolioParam = searchParams.get("portfolio");

  const [clients, setClients] = useState<MonitoringClientRow[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [initialPortfolioId] = useState(portfolioParam ? parseInt(portfolioParam, 10) : null);
  const [notes, setNotes] = useState<MeetingNote[]>([]);
  const [selectedNoteId, setSelectedNoteId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Form states
  const [showNewNoteForm, setShowNewNoteForm] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    meeting_date: new Date().toISOString().split("T")[0],
    meeting_type: "meeting" as MeetingNoteType,
    note_body: "",
    call_transcript: ""
  });

  // Summary state
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [expandedTranscriptIds, setExpandedTranscriptIds] = useState<Set<number>>(new Set());

  // Pre-call brief state
  const [showPreCallBrief, setShowPreCallBrief] = useState(false);
  const [preCallBrief, setPreCallBrief] = useState<PreCallBriefResponse | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(false);

  // Filter by note type
  const [noteTypeFilter, setNoteTypeFilter] = useState<"all" | MeetingNoteType>("all");

  // Filter by note content search
  const [noteSearchQuery, setNoteSearchQuery] = useState<string>("");

  // Filter out generic client names (e.g., "Client 6", "Client 22")
  const isGenericClientName = (name: string) => /^Client\s+\d+$/i.test(name);

  // Memoized selected note to ensure it updates when notes change
  const selectedNote = useMemo(
    () => notes.find((n) => n.id === selectedNoteId),
    [notes, selectedNoteId]
  );

  // Memoized filtered clients for search
  const filteredClients = useMemo(() => {
    return clients
      .filter((c) => !isGenericClientName(c.client_name))
      .filter((c) =>
        c.client_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.client_id.toString().includes(searchQuery)
      )
      .sort((a, b) => a.client_name.localeCompare(b.client_name));
  }, [clients, searchQuery]);

  // Memoized filtered notes by type and search query
  const filteredNotes = useMemo(() => {
    let filtered = notes;

    // Filter by type
    if (noteTypeFilter !== "all") {
      filtered = filtered.filter((n) => n.meeting_type === noteTypeFilter);
    }

    // Filter by search query
    if (noteSearchQuery.trim()) {
      const query = noteSearchQuery.toLowerCase();
      filtered = filtered.filter((n) =>
        n.title.toLowerCase().includes(query) ||
        n.note_body.toLowerCase().includes(query) ||
        (n.call_transcript && n.call_transcript.toLowerCase().includes(query)) ||
        (n.ai_summary && n.ai_summary.toLowerCase().includes(query))
      );
    }

    return filtered;
  }, [notes, noteTypeFilter, noteSearchQuery]);

  // Count notes by type for tabs
  const noteTypeCounts = useMemo(() => {
    return {
      all: notes.length,
      meeting: notes.filter((n) => n.meeting_type === "meeting").length,
      phone_call: notes.filter((n) => n.meeting_type === "phone_call").length,
      email: notes.filter((n) => n.meeting_type === "email").length,
      review: notes.filter((n) => n.meeting_type === "review").length,
    };
  }, [notes]);

  // Load clients on mount
  useEffect(() => {
    const loadClients = async () => {
      try {
        const summary = await fetchMonitoringSummary();
        if (summary) {
          const detail = await import("../../lib/api").then((m) =>
            m.fetchMonitoringDetail ? m.fetchMonitoringDetail() : null
          );
          if (detail?.clients) {
            const filtered = detail.clients.filter((c) => !isGenericClientName(c.client_name));
            setClients(filtered);
            if (filtered.length > 0) {
              // Try to select client based on portfolio param if provided
              if (initialPortfolioId) {
                // Try to find a client with matching portfolio
                const matchingClient = filtered.find((c) => c.client_id === initialPortfolioId);
                setSelectedClientId(matchingClient ? matchingClient.client_id : filtered[0].client_id);
              } else {
                setSelectedClientId(filtered[0].client_id);
              }
            }
          }
        }
      } catch (e) {
        setError((e as Error).message);
      }
    };
    void loadClients();
  }, [initialPortfolioId]);

  // Handle click outside dropdown to close it
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        searchInputRef.current &&
        !searchInputRef.current.contains(e.target as Node)
      ) {
        setShowSearchDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Load notes when client changes
  useEffect(() => {
    if (!selectedClientId) return;

    const loadNotes = async () => {
      setLoading(true);
      setError(null);
      setSummaryError(null);
      try {
        const response = await fetchMeetingNotes(selectedClientId, { limit: 50 });
        setNotes(response.items);
        setSelectedNoteId(null);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    };
    void loadNotes();
  }, [selectedClientId]);

  const handleCreateNote = async () => {
    if (!selectedClientId || !formData.title || !formData.note_body) {
      setError("Please fill in required fields");
      return;
    }

    try {
      setLoading(true);
      const newNote = await createMeetingNote(selectedClientId, formData as MeetingNoteCreate);
      setNotes([newNote, ...notes]);
      setFormData({
        title: "",
        meeting_date: new Date().toISOString().split("T")[0],
        meeting_type: "meeting",
        note_body: "",
        call_transcript: ""
      });
      setShowNewNoteForm(false);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSummarizeTranscript = async (noteId: number) => {
    try {
      setSummarizing(true);
      setSummaryError(null);
      const response = await summarizeTranscript(noteId);
      // Update the note in the list AND refresh selected detail
      const updatedNotes = notes.map((n) => (n.id === noteId ? response.note : n));
      setNotes(updatedNotes);
      // Keep the same note selected so user can see the summary immediately
      setSelectedNoteId(noteId);
    } catch (e) {
      setSummaryError((e as Error).message);
    } finally {
      setSummarizing(false);
    }
  };

  const handleToggleActionItem = async (noteId: number, index: number, currentCompleted: boolean) => {
    try {
      const response = await updateActionItem(noteId, index, !currentCompleted);
      // Update the note in the list
      const updatedNotes = notes.map((n) => (n.id === noteId ? response.note : n));
      setNotes(updatedNotes);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleOpenPreCallBrief = async () => {
    if (!selectedClientId) return;
    try {
      setLoadingBrief(true);
      const brief = await fetchPreCallBrief(selectedClientId);
      setPreCallBrief(brief);
      setShowPreCallBrief(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingBrief(false);
    }
  };

  const selectedClient = clients.find((c) => c.client_id === selectedClientId);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="page-title">Meeting Notes</h1>
        <p className="page-subtitle">
          Log client meetings and conversations. AI extracts summaries and action items from transcripts.
        </p>
      </header>

      {error && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Pre-Call Brief Modal */}
      {showPreCallBrief && preCallBrief && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="sticky top-0 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-200 p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Pre-Call Brief</h2>
                  <p className="text-sm text-gray-600 mt-1">{preCallBrief.client_name}</p>
                </div>
                <button
                  onClick={() => setShowPreCallBrief(false)}
                  className="text-gray-500 hover:text-gray-700 text-2xl w-8 h-8 flex items-center justify-center"
                >
                  ×
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              {/* Portfolio Context Card */}
              <div className="card p-4 bg-blue-50 border-blue-200 space-y-3">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-900">Portfolio Context</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-blue-700">Risk Profile</div>
                    <div className="text-lg font-semibold text-blue-900">{preCallBrief.risk_profile}</div>
                  </div>
                  <div>
                    <div className="text-xs text-blue-700">Total AUM</div>
                    <div className="text-lg font-semibold text-blue-900">
                      ${(preCallBrief.aum / 1000000).toFixed(2)}M
                    </div>
                  </div>
                </div>
              </div>

              {/* Open Alerts Card */}
              <div className="card p-4 bg-red-50 border-red-200 space-y-3">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-red-900">Open Alerts</div>
                <div className="flex items-center gap-2">
                  <span className="text-3xl font-bold text-red-600">{preCallBrief.open_alert_count}</span>
                  <div className="flex-1">
                    <div className="text-sm text-red-900">Active alert{preCallBrief.open_alert_count !== 1 ? "s" : ""}</div>
                    {preCallBrief.highest_priority && (
                      <div className="text-xs text-red-700 mt-1">
                        Highest: <span className="font-semibold">{preCallBrief.highest_priority}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Last Interaction Card */}
              {preCallBrief.last_note_title ? (
                <div className="card p-4 bg-emerald-50 border-emerald-200 space-y-3">
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-900">Last Interaction</div>
                  <div className="space-y-2">
                    <div>
                      <div className="text-sm font-semibold text-emerald-900">{preCallBrief.last_note_title}</div>
                      {preCallBrief.last_note_date && (
                        <div className="text-xs text-emerald-700 mt-0.5">
                          {new Date(preCallBrief.last_note_date).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                    {preCallBrief.last_note_summary && (
                      <p className="text-sm text-emerald-900 mt-2 line-clamp-3">
                        {preCallBrief.last_note_summary}
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="card p-4 bg-gray-50 border-gray-200">
                  <div className="text-xs text-gray-600">No previous notes on record</div>
                </div>
              )}

              {/* Outstanding Action Items Card */}
              {preCallBrief.outstanding_action_items.length > 0 ? (
                <div className="card p-4 bg-amber-50 border-amber-200 space-y-3">
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-900">
                    Outstanding Action Items
                  </div>
                  <ul className="space-y-2">
                    {preCallBrief.outstanding_action_items.map((item, idx) => (
                      <li key={idx} className="flex gap-2 text-sm text-amber-900">
                        <span className="font-semibold flex-shrink-0">{idx + 1}.</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="card p-4 bg-green-50 border-green-200">
                  <div className="text-sm text-green-900 font-semibold">✓ All action items complete</div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 p-4 flex justify-end">
              <Button onClick={() => setShowPreCallBrief(false)} variant="primary">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Client Selector and Create Note Button */}
      <div className="card p-4 md:p-5 space-y-3">
        <div className="flex flex-col md:flex-row gap-3 items-start md:items-end">
          <div className="flex-1 w-full">
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted mb-2">
              Search Client
            </label>
            <div className="relative w-full">
              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                <Search className="w-4 h-4" />
              </div>
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setShowSearchDropdown(true);
                }}
                onFocus={() => setShowSearchDropdown(true)}
                placeholder="Type client name..."
                className="w-full pl-9 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:border-blue-500"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Autocomplete Dropdown - Part of Normal Flow */}
            {showSearchDropdown && (
              <div className="bg-white border border-t-0 border-gray-300 rounded-b-lg shadow-sm max-h-64 overflow-y-auto scrollbar-hide z-10 w-full">
                {filteredClients.length === 0 ? (
                  <div className="p-3 text-sm text-gray-500 text-center">
                    No clients found
                  </div>
                ) : (
                  filteredClients.map((client) => (
                    <button
                      key={client.client_id}
                      onClick={() => {
                        setSelectedClientId(client.client_id);
                        setSearchQuery(client.client_name);
                        setShowSearchDropdown(false);
                      }}
                      className={`w-full text-left px-3 py-2.5 hover:bg-blue-50 border-b border-gray-100 last:border-b-0 transition-colors ${
                        selectedClientId === client.client_id
                          ? "bg-blue-100"
                          : ""
                      }`}
                    >
                      <div className="font-semibold text-sm text-gray-900">
                        {client.client_name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {client.portfolios_count} portfolios
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Button onClick={() => void handleOpenPreCallBrief()} disabled={!selectedClientId || loadingBrief} variant="secondary">
              {loadingBrief ? "Loading..." : "📋 Pre-Call Brief"}
            </Button>
            <Button onClick={() => setShowNewNoteForm(!showNewNoteForm)} variant="primary">
              {showNewNoteForm ? "Cancel" : "+ New Note"}
            </Button>
          </div>
        </div>

        {/* New Note Form */}
        {showNewNoteForm && (
          <div className="border-t border-gray-200 pt-4 mt-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Title</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder="e.g., Quarterly Review"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Date</label>
                <input
                  type="date"
                  value={formData.meeting_date}
                  onChange={(e) => setFormData({ ...formData, meeting_date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Type</label>
              <select
                value={formData.meeting_type}
                onChange={(e) => setFormData({ ...formData, meeting_type: e.target.value as MeetingNoteType })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
              >
                <option value="meeting">Meeting</option>
                <option value="phone_call">Phone Call</option>
                <option value="email">Email</option>
                <option value="review">Review</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Note Body</label>
              <textarea
                value={formData.note_body}
                onChange={(e) => setFormData({ ...formData, note_body: e.target.value })}
                placeholder="Enter meeting notes..."
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Call Transcript (Optional)
              </label>
              <textarea
                value={formData.call_transcript}
                onChange={(e) => setFormData({ ...formData, call_transcript: e.target.value })}
                placeholder="Paste call transcript here for AI summarization..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
            <Button onClick={() => void handleCreateNote()} disabled={loading} className="w-full">
              {loading ? "Creating..." : "Create Note"}
            </Button>
          </div>
        )}
      </div>

      {/* Notes List and Detail View */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1.8fr)] gap-3">
        {/* Notes List */}
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted px-1">
            Notes ({filteredNotes.length})
          </div>

          {/* Note Search Bar */}
          {notes.length > 0 && (
            <div className="relative px-1">
              <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                <Search className="w-4 h-4" />
              </div>
              <input
                type="text"
                value={noteSearchQuery}
                onChange={(e) => setNoteSearchQuery(e.target.value)}
                placeholder="Search notes..."
                className="w-full pl-9 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:border-blue-500"
              />
              {noteSearchQuery && (
                <button
                  onClick={() => setNoteSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          )}

          {/* Note Type Filter Tabs */}
          {notes.length > 0 && (
            <div className="flex gap-2 flex-wrap px-1">
              {(
                [
                  { label: "All", type: "all" as const, count: noteTypeCounts.all },
                  { label: "Meeting", type: "meeting" as const, count: noteTypeCounts.meeting },
                  { label: "Phone Call", type: "phone_call" as const, count: noteTypeCounts.phone_call },
                  { label: "Email", type: "email" as const, count: noteTypeCounts.email },
                  { label: "Review", type: "review" as const, count: noteTypeCounts.review },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.type}
                  onClick={() => setNoteTypeFilter(tab.type)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                    noteTypeFilter === tab.type
                      ? "bg-blue-100 text-blue-700 border border-blue-300"
                      : "bg-gray-100 text-gray-700 border border-gray-200 hover:bg-gray-150"
                  }`}
                >
                  {tab.label}
                  <span className="text-xs font-semibold bg-gray-300 px-1.5 py-0.5 rounded-full">
                    {tab.count}
                  </span>
                </button>
              ))}
            </div>
          )}
          {loading ? (
            <div className="card p-4 text-sm text-ws-muted">Loading notes...</div>
          ) : filteredNotes.length === 0 ? (
            <div className="card p-4 text-sm text-ws-muted">
              {notes.length === 0 ? "No notes yet. Create one to get started." : "No notes match this filter."}
            </div>
          ) : (
            filteredNotes.map((note) => (
              <div
                key={note.id}
                role="button"
                onClick={() => setSelectedNoteId(note.id)}
                className={`card p-3 cursor-pointer transition-colors ${
                  selectedNoteId === note.id
                    ? "border-gray-400 bg-gray-50"
                    : "hover:border-gray-400"
                }`}
              >
                <div className="flex items-start gap-2">
                  <FileText className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm text-gray-900 truncate">
                      {note.title}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {new Date(note.meeting_date).toLocaleDateString()}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                        {note.meeting_type.replace(/_/g, " ")}
                      </span>
                      {note.ai_summary && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 inline-flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          Summarized
                        </span>
                      )}
                      {note.ai_action_items && note.ai_action_items.length > 0 && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-semibold">
                          {note.action_item_completions?.filter(Boolean).length ?? 0}/{note.ai_action_items.length}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail View - Show filtered notes as cards with transcript accordions */}
        <div className="space-y-4 self-start w-full">
          {filteredNotes.length === 0 ? (
            <div className="card p-4 flex flex-col items-center justify-center space-y-3 py-10 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 text-gray-400">
                <FileText className="w-6 h-6" />
              </div>
              <div className="text-sm font-semibold text-gray-900">
                {notes.length === 0 ? "No Notes Yet" : "No Notes Match Filter"}
              </div>
              <div className="text-xs text-ws-muted">
                {notes.length === 0 ? "Create a note to get started." : "Try adjusting your filter."}
              </div>
            </div>
          ) : (
            filteredNotes.map((note, idx) => {
              // Auto-expand first transcript
              const isFirstNote = idx === 0;
              const isExpanded = expandedTranscriptIds.has(note.id) || isFirstNote;

              const cleanTranscript = (transcript: string) => {
                return transcript
                  .replace(/\[SCENE START\]\n*/gi, "")
                  .replace(/\[SCENE END\]\n*/gi, "")
                  .trim();
              };

              return (
                <div
                  key={note.id}
                  className={`card p-4 space-y-3 border-l-4 ${
                    selectedNoteId === note.id
                      ? "border-l-blue-500 bg-blue-50"
                      : "border-l-gray-300 hover:border-l-gray-400"
                  }`}
                  role="button"
                  onClick={() => setSelectedNoteId(note.id)}
                >
                  {/* Note Header */}
                  <div>
                    <div className="text-sm font-semibold text-gray-900">{note.title}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      {new Date(note.meeting_date).toLocaleDateString()} ·{" "}
                      {note.meeting_type.replace(/_/g, " ")}
                    </div>
                  </div>

                  {/* Note Body */}
                  <div className="border-t border-gray-200 pt-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-gray-700 mb-2">
                      Note
                    </div>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-2">
                      {note.note_body}
                    </p>
                  </div>

                  {/* Transcript Accordion */}
                  {note.call_transcript && (
                    <div className="border-t border-gray-200 pt-3">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedTranscriptIds((prev) => {
                            const next = new Set(prev);
                            if (next.has(note.id)) {
                              next.delete(note.id);
                            } else {
                              next.add(note.id);
                            }
                            return next;
                          });
                        }}
                        className="flex items-center gap-2 text-sm font-semibold text-gray-900 hover:text-gray-700 w-full"
                      >
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                        Call Transcript
                      </button>
                      {isExpanded && (
                        <div className="mt-3 p-3 bg-gray-50 rounded border border-gray-200 text-xs text-gray-700 max-h-64 overflow-y-auto whitespace-pre-wrap font-mono leading-relaxed">
                          {cleanTranscript(note.call_transcript)}
                        </div>
                      )}
                    </div>
                  )}

                  {/* AI Summary */}
                  {note.ai_summary ? (
                    <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                        <div className="text-xs font-semibold text-emerald-900">AI Summary</div>
                      </div>
                      <p className="text-sm text-emerald-900 leading-relaxed">
                        {note.ai_summary}
                      </p>
                      {note.ai_action_items && note.ai_action_items.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-emerald-900">Action Items</div>
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-200 text-emerald-900 font-semibold">
                              {note.action_item_completions?.filter(Boolean).length ?? 0}/{note.ai_action_items.length} Complete
                            </span>
                          </div>
                          <ul className="text-sm text-emerald-900 space-y-2">
                            {note.ai_action_items.map((item, itemIdx) => {
                              const isCompleted = note.action_item_completions?.[itemIdx] ?? false;
                              return (
                                <li key={itemIdx} className="flex items-start gap-2">
                                  <input
                                    type="checkbox"
                                    checked={isCompleted}
                                    onChange={() => void handleToggleActionItem(note.id, itemIdx, isCompleted)}
                                    className="mt-0.5 w-4 h-4 rounded border-emerald-300 text-emerald-600 cursor-pointer flex-shrink-0"
                                  />
                                  <span className={isCompleted ? "line-through opacity-50" : ""}>
                                    {item}
                                  </span>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : note.call_transcript ? (
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleSummarizeTranscript(note.id);
                      }}
                      disabled={summarizing}
                      className="w-full"
                      variant="secondary"
                    >
                      {summarizing ? "Summarizing..." : "AI Summarize Transcript"}
                    </Button>
                  ) : null}

                  {summaryError && (
                    <div className="rounded-lg border border-red-200 bg-red-50 p-3 flex gap-2">
                      <AlertCircle className="w-4 h-4 text-red-700 flex-shrink-0 mt-0.5" />
                      <div className="text-xs text-red-700">
                        <div className="font-semibold mb-0.5">Summary Failed</div>
                        {summaryError}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
