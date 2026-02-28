export default function LoadingMeetingNotesPage() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-64 rounded-lg skeleton-shimmer" />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="h-32 rounded-xl skeleton-shimmer" />
        <div className="h-32 rounded-xl skeleton-shimmer" />
        <div className="h-32 rounded-xl skeleton-shimmer" />
      </div>
      <div className="h-96 rounded-xl skeleton-shimmer" />
    </div>
  );
}
