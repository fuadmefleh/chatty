import type { InputHTMLAttributes } from 'react';

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

const Checkbox: React.FC<CheckboxProps> = ({ label, id, className = '', ...props }) => (
  <label htmlFor={id} className="flex items-center gap-2 text-sm text-ink-dim">
    <input
      type="checkbox"
      id={id}
      className={`h-4 w-4 rounded border-line accent-signal ${className}`}
      {...props}
    />
    {label}
  </label>
);

export default Checkbox;
