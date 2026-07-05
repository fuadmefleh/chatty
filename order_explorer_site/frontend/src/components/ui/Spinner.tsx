const sizeClasses: Record<'sm' | 'md' | 'lg', string> = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-9 w-9 border-[3px]',
};

const Spinner: React.FC<{ size?: 'sm' | 'md' | 'lg'; label?: string }> = ({ size = 'md', label = 'Loading' }) => (
  <span className="inline-flex items-center gap-2 text-muted" role="status" aria-live="polite">
    <span
      className={`inline-block animate-spin rounded-full border-line border-t-signal motion-reduce:animate-[spin_1.5s_linear_infinite] ${sizeClasses[size]}`}
      aria-hidden="true"
    />
    <span className="text-sm">{label}</span>
  </span>
);

export default Spinner;
