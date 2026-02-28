"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/Buttons";
import {
  fetchMonitoringSummary,
  fetchMeetingNotes,
  createMeetingNote,
  summarizeTranscript
} from "../../lib/api";
import type {
  MonitoringUniverseSummary,
  MonitoringClientRow,
  MeetingNote,
  MeetingNoteCreate,
  MeetingNoteType
} from "../../lib/types";
import { ChevronDown, ChevronUp, FileText, CheckCircle2, AlertCircle } from "lucide-react";

export default function MeetingNotesPage() {
  const [clients, setClients] = useState<MonitoringClientRow[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [notes, setNotes] = useState<MeetingNote[]>([]);
  const [selectedNoteId, setSelectedNoteId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  // Memoized selected note to ensure it updates when notes change
  const selectedNote = useMemo(
    () => notes.find((n) => n.id === selectedNoteId),
    [notes, selectedNoteId]
  );

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
            setClients(detail.clients);
            if (detail.clients.length > 0) {
              setSelectedClientId(detail.clients[0].client_id);
            }
          }
        }
      } catch (e) {
        setError((e as Error).message);
      }
    };
    void loadClients();
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

      {/* Client Selector and Create Note Button */}
      <div className="card p-4 md:p-5 space-y-3">
        <div className="flex flex-col md:flex-row gap-3 items-start md:items-end">
          <div className="flex-1">
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted mb-2">
              Select Client
            </label>
            <select
              value={selectedClientId ?? ""}
              onChange={(e) => setSelectedClientId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
            >
              {clients.map((client) => (
                <option key={client.client_id} value={client.client_id}>
                  {client.client_name} ({client.portfolios_count} portfolios)
                </option>
              ))}
            </select>
          </div>
          <Button onClick={() => setShowNewNoteForm(!showNewNoteForm)} variant="primary">
            {showNewNoteForm ? "Cancel" : "+ New Note"}
          </Button>
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
            Notes ({notes.length})
          </div>
          {loading ? (
            <div className="card p-4 text-sm text-ws-muted">Loading notes...</div>
          ) : notes.length === 0 ? (
            <div className="card p-4 text-sm text-ws-muted">
              No notes yet. Create one to get started.
            </div>
          ) : (
            notes.map((note) => (
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
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail View - Show all notes as cards with transcript accordions */}
        <div className="space-y-4 self-start w-full">
          {notes.length === 0 ? (
            <div className="card p-4 flex flex-col items-center justify-center space-y-3 py-10 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 text-gray-400">
                <FileText className="w-6 h-6" />
              </div>
              <div className="text-sm font-semibold text-gray-900">No Notes Yet</div>
              <div className="text-xs text-ws-muted">
                Create a note to get started.
              </div>
            </div>
          ) : (
            notes.map((note, idx) => {
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
                        <div className="mt-3 space-y-1">
                          <div className="text-xs font-semibold text-emerald-900">Action Items</div>
                          <ul className="text-sm text-emerald-900 space-y-1">
                            {note.ai_action_items.map((item, itemIdx) => (
                              <li key={itemIdx} className="flex gap-2">
                                <span>•</span>
                                <span>{item}</span>
                              </li>
                            ))}
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
