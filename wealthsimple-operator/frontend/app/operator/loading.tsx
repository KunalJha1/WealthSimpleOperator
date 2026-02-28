export default function LoadingOperatorPage() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-64 rounded-lg skeleton-shimmer" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="h-20 rounded-xl skeleton-shimmer" />
        <div className="h-20 rounded-xl skeleton-shimmer" />
        <div className="h-20 rounded-xl skeleton-shimmer" />
        <div className="h-20 rounded-xl skeleton-shimmer" />
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.8fr)_minmax(280px,0.8fr)]">
        <div className="space-y-3">
          <div className="h-40 rounded-xl skeleton-shimmer" />
          <div className="h-40 rounded-xl skeleton-shimmer" />
        </div>
        <div className="h-96 rounded-xl skeleton-shimmer" />
      </div>
    </div>
  );
}
