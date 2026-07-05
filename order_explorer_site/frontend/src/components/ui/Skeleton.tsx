interface SkeletonProps {
  className?: string;
}

/** A shimmering placeholder block for loading states. */
const Skeleton: React.FC<SkeletonProps> = ({ className = 'h-4 w-full' }) => (
  <div className={`animate-pulse rounded-md bg-surface-dim ${className}`} aria-hidden="true" />
);

export const SkeletonRows: React.FC<{ rows?: number; className?: string }> = ({ rows = 3, className }) => (
  <div className="flex flex-col gap-2" role="status" aria-label="Loading">
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} className={className ?? 'h-4 w-full'} />
    ))}
  </div>
);

export default Skeleton;
