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

    try {
      if (mode === "signup") {
        const siteUrl =
          process.env.NEXT_PUBLIC_SITE_URL ||
          process.env.NEXT_PUBLIC_VERCEL_URL ||
          (typeof window !== "undefined" ? window.location.origin : "");
        const normalizedSiteUrl = siteUrl.startsWith("http")
          ? siteUrl
          : `https://${siteUrl}`;
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { full_name: fullName },
            emailRedirectTo: `${normalizedSiteUrl.replace(/\/$/, "")}/dashboard`
          }
        });
        if (error) throw error;
        setMessage(
          "Account created. Check your email for verification. After confirming, you will be redirected back to dashboard."
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
      </section>
    </main>
  );
}
