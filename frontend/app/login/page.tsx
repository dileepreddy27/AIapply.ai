"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "../../lib/supabase";

type AuthMode = "signin" | "signup";

export default function LoginPage() {
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
    () => (mode === "signin" ? "Welcome back" : "Create your account"),
    [mode]
  );

  async function signInWithGoogle() {
    setMessage("");
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${resolveSiteUrl()}/dashboard` }
      });
      if (error) throw error;
      // Supabase redirects the browser to Google on success.
    } catch (err) {
      const text = err instanceof Error ? err.message : "Google sign-in failed.";
      setMessage(
        /provider is not enabled|unsupported provider/i.test(text)
          ? "Google sign-in isn't enabled yet. Enable the Google provider in Supabase Auth, or continue with email below."
          : text
      );
    }
  }

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

        if (data.session) {
          router.push("/dashboard");
          return;
        }

        const identities = data.user?.identities;
        if (identities && identities.length === 0) {
          setMode("signin");
          setMessage(
            "This email is already registered. Please sign in below, or use \"Forgot password\" to reset it."
          );
          return;
        }

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
    <main className="auth-split">
      {/* Left: editorial */}
      <section className="auth-left">
        <Link href="/" className="lp-logo auth-left-brand">AIapply.ai</Link>
        <div className="auth-left-body">
          <p className="lp-eyebrow">Made for job seekers</p>
          <h1>Be first to every job that fits you.</h1>
          <p className="auth-left-sub">
            Match, tailor, and apply — with every change shown to you first. Three things,
            done well:
          </p>
          <ul className="auth-bullets">
            <li>Match you with roles from Greenhouse, Lever, and Ashby</li>
            <li>Tailor your resume and cover letter to each role</li>
            <li>Queue and apply with consent-first automation</li>
          </ul>
        </div>
      </section>

      {/* Right: auth panel */}
      <section className="auth-right">
        <div className="auth-panel">
          <h2>{mode === "signin" ? "Welcome back" : "Create your account"}</h2>
          <p className="auth-panel-sub">Start free — no card required.</p>

          <button type="button" className="oauth-btn" onClick={signInWithGoogle}>
            <span className="oauth-g" aria-hidden="true">G</span>
            Continue with Google
          </button>

          <div className="auth-divider"><span>Or continue with email</span></div>

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
              Email address
              <input
                type="email"
                placeholder="you@example.com"
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
            <button type="submit" className="auth-primary" disabled={loading}>
              {loading ? "Please wait..." : mode === "signin" ? "Continue" : "Create account"}
            </button>
          </form>

          {message && <p className="status">{message}</p>}

          {awaitingConfirmation && (
            <button
              type="button"
              className="switch resend"
              onClick={resendConfirmation}
              disabled={loading}
            >
              {loading ? "Please wait..." : "Resend verification email"}
            </button>
          )}

          <p className="auth-fineprint">
            By continuing you agree to our Terms of Service and Privacy Policy.
          </p>
          <p className="auth-foot">
            <Link href="/">← Back to home</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
