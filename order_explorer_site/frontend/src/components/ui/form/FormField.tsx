import type { PropsWithChildren, ReactNode } from 'react';
import { useId } from 'react';

interface FormFieldProps {
  label: string;
  hint?: ReactNode;
  error?: string;
  htmlFor?: string;
}

/** Label + control + hint/error wrapper. Pass `htmlFor` matching the control's id. */
const FormField: React.FC<PropsWithChildren<FormFieldProps>> = ({ label, hint, error, htmlFor, children }) => {
  const generatedId = useId();
  const id = htmlFor ?? generatedId;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink-dim">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-xs text-alert-red" role="alert">
          {error}
        </p>
      ) : (
        hint && <p className="text-xs text-muted">{hint}</p>
      )}
    </div>
  );
};

export default FormField;
