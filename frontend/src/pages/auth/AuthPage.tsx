/**
 * RegisterForm — email + password + display name.
 * Maps to POST /api/v1/auth/register → AuthResponseOut
 */

import { useState } from "react";

import { Alert, Button, Input, PasswordStrength } from "@/components/ui";
import { useFormValidation, rules } from "@/hooks/useFormValidation";
import { useAuthActions, useAuthLoading } from "@/store/authStore";
import { AuthApiError } from "@/api/client";

interface RegisterFormFields {
  display_name: string;
  email: string;
  password: string;
  confirm_password: string;
}

interface Props {
  onSuccess?: () => void;
}

export default function RegisterForm({ onSuccess }: Props) {
  const { register } = useAuthActions();
  const isLoading = useAuthLoading();

  const [fields, setFields] = useState<RegisterFormFields>({
    display_name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [apiError, setApiError] = useState<string | null>(null);

  const { errors, validate, clearError } = useFormValidation<RegisterFormFields>({
    display_name: [rules.minLength(2)],
    email: [rules.required("Email"), rules.email()],
    password: [rules.required("Password"), rules.password()],
    confirm_password: [
      rules.required("Confirm password"),
      rules.match(fields.password),
    ],
  });

  const handleChange = (field: keyof RegisterFormFields) => (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setFields((prev) => ({ ...prev, [field]: e.target.value }));
    clearError(field);
    setApiError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate(fields)) return;

    try {
      await register({
        email: fields.email,
        password: fields.password,
        display_name: fields.display_name.trim() || undefined,
      });
      onSuccess?.();
    } catch (err) {
      if (err instanceof AuthApiError) {
        setApiError(err.detail);
      } else {
        setApiError("Registration failed. Please try again.");
      }
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <h2 className="auth-form__title">Create account</h2>
      <p className="auth-form__subtitle">Start your emotion-driven music journey</p>

      {apiError && (
        <Alert
          variant="error"
          message={apiError}
          onDismiss={() => setApiError(null)}
        />
      )}

      <Input
        label="Display name"
        type="text"
        autoComplete="name"
        value={fields.display_name}
        onChange={handleChange("display_name")}
        error={errors.display_name}
        hint="Optional — shown on your profile"
        disabled={isLoading}
        placeholder="Jane Smith"
      />

      <Input
        label="Email address"
        type="email"
        autoComplete="email"
        value={fields.email}
        onChange={handleChange("email")}
        error={errors.email}
        required
        disabled={isLoading}
        inputMode="email"
      />

      <div className="field-group">
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          value={fields.password}
          onChange={handleChange("password")}
          error={errors.password}
          required
          disabled={isLoading}
        />
        <PasswordStrength password={fields.password} />
      </div>

      <Input
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        value={fields.confirm_password}
        onChange={handleChange("confirm_password")}
        error={errors.confirm_password}
        required
        disabled={isLoading}
      />

      <Button type="submit" isLoading={isLoading} fullWidth>
        Create account
      </Button>

      <p className="auth-form__legal">
        By creating an account you agree to our{" "}
        <a href="/terms" className="auth-form__link">
          Terms of Service
        </a>{" "}
        and{" "}
        <a href="/privacy" className="auth-form__link">
          Privacy Policy
        </a>
        .
      </p>
    </form>
  );
}