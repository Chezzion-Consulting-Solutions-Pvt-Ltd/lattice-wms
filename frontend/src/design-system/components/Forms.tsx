import type { InputHTMLAttributes, LabelHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react';
import './components.css';

type FieldProps = {
  label: string;
  error?: string;
  children: ReactNode;
};

export function FormField({ label, error, children }: FieldProps) {
  return (
    <label className="lattice-form-field">
      <span className="lattice-form-label">{label}</span>
      {children}
      {error ? <span className="lattice-form-error">{error}</span> : null}
    </label>
  );
}

export function FormLabel({ children, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className="lattice-form-label" {...props}>
      {children}
    </label>
  );
}

export function FormError({ children }: { children: ReactNode }) {
  return <span className="lattice-form-error">{children}</span>;
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`lattice-input ${props.className ?? ''}`} {...props} />;
}

export function SearchInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <Input type="search" placeholder="Search" aria-label="Search" {...props} />;
}

export function PasswordInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <Input type="password" autoComplete="current-password" {...props} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`lattice-textarea ${props.className ?? ''}`} {...props} />;
}
