import { useCallback, useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export type Rule<T> = (value: T) => string | undefined;

export type FieldRules<F extends Record<string, any>> = {
  [K in keyof F]?: Rule<F[K]>[];
};

export type Errors<F extends Record<string, any>> =
  Partial<Record<keyof F, string>>;

// ─── Built-in rules ───────────────────────────────────────────────────────────

export const rules = {
  required: (label = "This field"): Rule<string> => (v) =>
    v.trim() ? undefined : `${label} is required.`,

  email: (): Rule<string> => (v) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
      ? undefined
      : "Enter a valid email address.",

  minLength: (n: number): Rule<string> => (v) =>
    v.length >= n ? undefined : `Must be at least ${n} characters.`,

  maxLength: (n: number): Rule<string> => (v) =>
    v.length <= n ? undefined : `Must be at most ${n} characters.`,

  password: (): Rule<string> => (v) => {
    if (v.length < 8) return "Password must be at least 8 characters.";
    if (!/[A-Z]/.test(v)) return "Include at least one uppercase letter.";
    if (!/[0-9]/.test(v)) return "Include at least one number.";
    return undefined;
  },

  match:
    (otherValue: string, label = "Fields"): Rule<string> =>
    (v) =>
      v === otherValue ? undefined : `${label} do not match.`,
};

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useFormValidation<F extends Record<string, any>>(
  fieldRules: FieldRules<F>
) {
  const [errors, setErrors] = useState<Errors<F>>({});

  const validate = useCallback(
    (values: F): boolean => {
      const next: Errors<F> = {};
      let valid = true;

      for (const key in fieldRules) {
        const fieldKey = key as keyof F;
        const rulesForField = fieldRules[fieldKey] ?? [];

        for (const rule of rulesForField) {
          const msg = rule(values[fieldKey]);

          if (msg) {
            next[fieldKey] = msg;
            valid = false;
            break;
          }
        }
      }

      setErrors(next);
      return valid;
    },
    [fieldRules]
  );

  const clearError = useCallback((field: keyof F) => {
    setErrors((prev) => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }, []);

  const clearAll = useCallback(() => setErrors({}), []);

  return { errors, validate, clearError, clearAll };
}