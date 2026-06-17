/**
 * Minimal, accessible UI primitives used across the auth pages.
 * Styled via CSS variables from globals.css — no CSS-in-JS.
 */

import React, { forwardRef } from "react";

// ─── Input ────────────────────────────────────────────────────────────────────

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, id, className = "", ...rest }, ref) => {
    const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");
    const errorId = `${inputId}-error`;
    const hintId = `${inputId}-hint`;

    return (
      <div className={`field ${error ? "field--error" : ""} ${className}`}>
        <label htmlFor={inputId} className="field__label">
          {label}
        </label>
        <input
          ref={ref}
          id={inputId}
          className="field__input"
          aria-invalid={!!error}
          aria-describedby={
            [error && errorId, hint && hintId].filter(Boolean).join(" ") || undefined
          }
          {...rest}
        />
        {hint && !error && (
          <p id={hintId} className="field__hint">
            {hint}
          </p>
        )}
        {error && (
          <p id={errorId} className="field__error" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  },
);
Input.displayName = "Input";

// ─── Button ───────────────────────────────────────────────────────────────────

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  isLoading?: boolean;
  fullWidth?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  isLoading = false,
  fullWidth = false,
  children,
  disabled,
  className = "",
  ...rest
}) => (
  <button
    className={`btn btn--${variant} ${fullWidth ? "btn--full" : ""} ${className}`}
    disabled={disabled || isLoading}
    aria-busy={isLoading}
    {...rest}
  >
    {isLoading ? (
      <>
        <span className="btn__spinner" aria-hidden="true" />
        <span className="sr-only">Loading…</span>
      </>
    ) : (
      children
    )}
  </button>
);

// ─── SocialButton ─────────────────────────────────────────────────────────────

interface SocialButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  provider: "google" | "apple";
  isLoading?: boolean;
}

const PROVIDER_META = {
  google: {
    label: "Continue with Google",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path
          d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"
          fill="#4285F4"
        />
        <path
          d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"
          fill="#34A853"
        />
        <path
          d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
          fill="#FBBC05"
        />
        <path
          d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
          fill="#EA4335"
        />
      </svg>
    ),
  },
  apple: {
    label: "Continue with Apple",
    icon: (
      <svg width="18" height="18" viewBox="0 0 814 1000" aria-hidden="true" fill="currentColor">
        <path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-37.5-165.9-117.8c-70.3-97.7-126.3-245.5-126.3-385.5 0-213.5 139-326.5 275.8-326.5 73.2 0 133.4 47.8 178.5 47.8 43 0 110.8-50.9 195.4-50.9 31.2 0 113.3 2.9 177.1 105.9zm-209.1-239.3c31.2-37.5 53.6-89.8 53.6-142.2 0-7.3-.6-14.6-1.9-20.6-50.3 1.9-110.5 33.5-146.6 75.8-28.2 32.5-55.1 84.8-55.1 138.5 0 8.3 1.3 16.6 1.9 19.2 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 134.5-71.9z" />
      </svg>
    ),
  },
} as const;

export const SocialButton: React.FC<SocialButtonProps> = ({
  provider,
  isLoading = false,
  className = "",
  ...rest
}) => {
  const meta = PROVIDER_META[provider];
  return (
    <button
      className={`social-btn social-btn--${provider} ${className}`}
      disabled={isLoading}
      aria-busy={isLoading}
      aria-label={meta.label}
      {...rest}
    >
      {isLoading ? (
        <span className="btn__spinner" aria-hidden="true" />
      ) : (
        meta.icon
      )}
      <span>{meta.label}</span>
    </button>
  );
};

// ─── Divider ─────────────────────────────────────────────────────────────────

export const Divider: React.FC<{ label?: string }> = ({ label = "or" }) => (
  <div className="divider" role="separator" aria-label={label}>
    <span className="divider__line" aria-hidden="true" />
    <span className="divider__label">{label}</span>
    <span className="divider__line" aria-hidden="true" />
  </div>
);

// ─── Alert ───────────────────────────────────────────────────────────────────

interface AlertProps {
  variant?: "error" | "success" | "info";
  message: string;
  onDismiss?: () => void;
}

export const Alert: React.FC<AlertProps> = ({
  variant = "error",
  message,
  onDismiss,
}) => (
  <div className={`alert alert--${variant}`} role="alert" aria-live="polite">
    <span className="alert__message">{message}</span>
    {onDismiss && (
      <button
        className="alert__dismiss"
        onClick={onDismiss}
        aria-label="Dismiss"
        type="button"
      >
        ×
      </button>
    )}
  </div>
);

// ─── PasswordStrength ─────────────────────────────────────────────────────────

interface PasswordStrengthProps {
  password: string;
}

function getStrength(pw: string): { score: number; label: string } {
  if (!pw) return { score: 0, label: "" };
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  const labels = ["", "Weak", "Fair", "Good", "Strong", "Very strong"];
  return { score, label: labels[score] ?? "Very strong" };
}

export const PasswordStrength: React.FC<PasswordStrengthProps> = ({ password }) => {
  const { score, label } = getStrength(password);
  if (!password) return null;
  return (
    <div className="pw-strength" aria-label={`Password strength: ${label}`}>
      <div className="pw-strength__bars">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className={`pw-strength__bar pw-strength__bar--${
              i <= score
                ? score <= 1
                  ? "weak"
                  : score <= 3
                  ? "fair"
                  : "strong"
                : "empty"
            }`}
          />
        ))}
      </div>
      <span className="pw-strength__label">{label}</span>
    </div>
  );
};