export default function LoadingSimulationsPage() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-56 rounded-lg skeleton-shimmer" />
      <div className="h-24 rounded-xl skeleton-shimmer" />
      <div className="h-96 rounded-xl skeleton-shimmer" />
    </div>
  );
}
