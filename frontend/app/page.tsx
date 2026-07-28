"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";

type AuthMode = "signin" | "signup";

export default function HomePage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);

  function resolveSiteUrl(): string {
    const siteUrl =
      process.env.NEXT_PUBLIC_SITE_URL ||
      process.env.NEXT_PUBLIC_VERCEL_URL ||
      (typeof window !== "undefined" ? window.location.origin : "");
    const normalized = siteUrl.startsWith("http") ? siteUrl : `https://${siteUrl}`;
    return normalized.replace(/\/$/, "");
  }

  useEffect(() => {
    let mounted = true;
    async function bootstrap() {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;
      if (data.session) {
        router.push("/dashboard");
      }
    }
    bootstrap();
    return () => {
      mounted = false;
    };
  }, [router]);

  const title = useMemo(
    () => (mode === "signin" ? "Welcome Back" : "Create Your Account"),
    [mode]
  );

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    setAwaitingConfirmation(false);

    try {
      if (mode === "signup") {
        const emailRedirectTo = `${resolveSiteUrl()}/dashboard`;
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { full_name: fullName },
            emailRedirectTo
          }
        });
        if (error) throw error;

        // Email confirmation is disabled on the project: a session is returned
        // immediately, so skip the "check your email" message entirely.
        if (data.session) {
          router.push("/dashboard");
          return;
        }

        // Supabase returns a success with an empty identities array when the
        // email is already registered (to prevent user enumeration). No email
        // is sent in that case, so guide the user to sign in instead of waiting.
        const identities = data.user?.identities;
        if (identities && identities.length === 0) {
          setMode("signin");
          setMessage(
            "This email is already registered. Please sign in below, or use \"Forgot password\" to reset it."
          );
          return;
        }

        // A confirmation email is genuinely required.
        setAwaitingConfirmation(true);
        setMessage(
          `Account created. We sent a verification link to ${email}. Check your inbox and spam folder — if it doesn't arrive within a minute, use "Resend" below.`
        );
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password
        });
        if (error) throw error;
        router.push("/dashboard");
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "Authentication failed.";
      // If sign-in fails only because the address isn't confirmed yet, offer a resend.
      if (/email not confirmed|not confirmed|confirm your email/i.test(text)) {
        setAwaitingConfirmation(true);
        setMessage(
          `Your email address isn't verified yet. Check your inbox and spam for the link, or use "Resend" below.`
        );
      } else {
        setMessage(text);
      }
    } finally {
      setLoading(false);
    }
  }

  async function resendConfirmation() {
    if (!email) {
      setMessage("Enter your email address first, then click Resend.");
      return;
    }
    setLoading(true);
    try {
      const { error } = await supabase.auth.resend({
        type: "signup",
        email,
        options: { emailRedirectTo: `${resolveSiteUrl()}/dashboard` }
      });
      if (error) throw error;
      setMessage(
        `Verification email resent to ${email}. Check your inbox and spam folder.`
      );
    } catch (err) {
      const text = err instanceof Error ? err.message : "Could not resend the email.";
      setMessage(text);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <div className="bg-orb orb-a" />
      <div className="bg-orb orb-b" />
      <section className="auth-card">
        <p className="brand">AIapply.ai</p>
        <h1>{title}</h1>
        <p className="subtitle">
          Resume-aware job matching by role. Build a profile, sign in, and get
          role-specific recommendations.
        </p>

        <div className="switch-row">
          <button
            className={mode === "signin" ? "switch active" : "switch"}
            type="button"
            onClick={() => setMode("signin")}
          >
            Sign In
          </button>
          <button
            className={mode === "signup" ? "switch active" : "switch"}
            type="button"
            onClick={() => setMode("signup")}
          >
            Create Account
          </button>
        </div>

        <form onSubmit={onSubmit} className="auth-form">
          {mode === "signup" && (
            <label>
              Full Name
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "signin" ? "Sign In" : "Create Account"}
          </button>
        </form>

        {message && <p className="status">{message}</p>}

        {awaitingConfirmation && (
          <button
            type="button"
            className="switch"
            onClick={resendConfirmation}
            disabled={loading}
          >
            {loading ? "Please wait..." : "Resend verification email"}
          </button>
        )}
      </section>
    </main>
  );
}
