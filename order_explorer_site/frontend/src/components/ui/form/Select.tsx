import type { SelectHTMLAttributes } from 'react';

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

const Select: React.FC<SelectProps> = ({ className = '', children, ...props }) => (
  <select
    className={`w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-signal ${className}`}
    {...props}
  >
    {children}
  </select>
);

export default Select;
