"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase";

type MatchResult = {
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  rag_score: number;
  final_score: number;
  overlap_terms: string[];
  explanation: string;
};

function cleanPriceId(raw: string): string {
  return raw
    .replace(/\\n/g, "")
    .replace(/[\n\r\t]/g, "")
    .replace(/\\/g, "")
    .replace(/"/g, "")
    .replace(/'/g, "")
    .trim();
}

export default function DashboardPage() {
  const router = useRouter();
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";
  const rawPriceId = process.env.NEXT_PUBLIC_STRIPE_PRICE_ID ?? "";
  const priceId = cleanPriceId(rawPriceId);

  const [userEmail, setUserEmail] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  const [fullName, setFullName] = useState("");
  const [targetRole, setTargetRole] = useState("Software Engineer");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [workAuthorizationStatus, setWorkAuthorizationStatus] = useState("");
  const [needsSponsorship, setNeedsSponsorship] = useState(false);
  const [veteranStatus, setVeteranStatus] = useState("");
  const [raceEthnicity, setRaceEthnicity] = useState("");
  const [genderIdentity, setGenderIdentity] = useState("");
  const [disabilityStatus, setDisabilityStatus] = useState("");
  const [preferredLocations, setPreferredLocations] = useState("");
  const [willingToRelocate, setWillingToRelocate] = useState(false);
  const [salaryExpectation, setSalaryExpectation] = useState("");
  const [applicationSummary, setApplicationSummary] = useState("");
  const [autoApplyEnabled, setAutoApplyEnabled] = useState(false);
  const [autoApplyConsent, setAutoApplyConsent] = useState(false);
  const [requireApprovalBeforeApply, setRequireApprovalBeforeApply] = useState(true);
  const [workPreferences, setWorkPreferences] = useState("");
  const [companiesToAvoid, setCompaniesToAvoid] = useState("");
  const [maxApplicationsPerDay, setMaxApplicationsPerDay] = useState("10");
  const [minimumMatchScore, setMinimumMatchScore] = useState("80");

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [results, setResults] = useState<MatchResult[]>([]);
  const [roleSuggestions, setRoleSuggestions] = useState<string[]>([]);

  const canRunMatch = useMemo(() => !!token && !!resumeFile, [token, resumeFile]);

  useEffect(() => {
    let mounted = true;
    async function bootstrap() {
      const { data } = await supabase.auth.getSession();
      const session = data.session;
      if (!session) {
        router.push("/");
        return;
      }
      if (!mounted) return;
      setToken(session.access_token);
      setUserEmail(session.user.email ?? "");
      setLoading(false);
      await Promise.all([
        loadProfile(session.access_token),
        fetchRoleSuggestions("", session.access_token),
      ]);
    }
    bootstrap();
    return () => {
      mounted = false;
    };
  }, [router]);

  function isBackendConfigured(): boolean {
    return !!backendUrl && /^https?:\/\//.test(backendUrl);
  }

  function backendConfigMessage(): string {
    return "Backend URL is not configured. Set NEXT_PUBLIC_BACKEND_URL in Vercel env and redeploy.";
  }

  async function authFetch(url: string, options?: RequestInit): Promise<Response> {
    return fetch(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options?.headers ?? {})
      }
    });
  }

  async function fetchRoleSuggestions(query: string, accessToken: string = token): Promise<void> {
    if (!isBackendConfigured()) return;
    try {
      const res = await fetch(
        `${backendUrl}/api/roles/search?q=${encodeURIComponent(query)}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      const data = await res.json();
      setRoleSuggestions(Array.isArray(data?.roles) ? data.roles : []);
    } catch {
      // silently ignore suggestions failures
    }
  }

  async function loadProfile(accessToken: string): Promise<void> {
    try {
      const res = await fetch(`${backendUrl}/api/profile/me`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      const data = await res.json();
      const profile = data?.profile;
      if (!profile) return;
      setFullName(profile.full_name ?? "");
      setTargetRole(profile.target_role || "Software Engineer");
      setExperienceLevel(profile.experience_level ?? "");
      setSkillsText((profile.skills || []).join(", "));

      const app = profile.application_profile || {};
      setPhone(app.phone ?? "");
      setLocation(app.location ?? "");
      setLinkedinUrl(app.linkedin_url ?? "");
      setPortfolioUrl(app.portfolio_url ?? "");
      setWorkAuthorizationStatus(app.work_authorization_status ?? "");
      setNeedsSponsorship(Boolean(app.needs_sponsorship));
      setVeteranStatus(app.veteran_status ?? "");
      setRaceEthnicity(app.race_ethnicity ?? "");
      setGenderIdentity(app.gender_identity ?? "");
      setDisabilityStatus(app.disability_status ?? "");
      setPreferredLocations(app.preferred_locations ?? "");
      setWillingToRelocate(Boolean(app.willing_to_relocate));
      setSalaryExpectation(app.salary_expectation ?? "");
      setApplicationSummary(app.summary ?? "");
      setAutoApplyEnabled(Boolean(app.auto_apply_enabled));
      setAutoApplyConsent(Boolean(app.auto_apply_consent));
      setRequireApprovalBeforeApply(Boolean(app.require_approval_before_apply ?? true));
      setWorkPreferences((app.work_preferences || []).join(", "));
      setCompaniesToAvoid(app.companies_to_avoid ?? "");
      setMaxApplicationsPerDay(String(app.max_applications_per_day ?? 10));
      setMinimumMatchScore(String(app.minimum_match_score ?? 80));
    } catch (err) {
      console.error(err);
    }
  }

  async function saveProfile(): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    try {
      const skills = skillsText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const payload = {
        work_preferences: workPreferences
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        full_name: fullName,
        target_role: targetRole,
        skills,
        experience_level: experienceLevel,
        phone,
        location,
        linkedin_url: linkedinUrl,
        portfolio_url: portfolioUrl,
        work_authorization_status: workAuthorizationStatus,
        needs_sponsorship: needsSponsorship,
        veteran_status: veteranStatus,
        race_ethnicity: raceEthnicity,
        gender_identity: genderIdentity,
        disability_status: disabilityStatus,
        preferred_locations: preferredLocations,
        willing_to_relocate: willingToRelocate,
        salary_expectation: salaryExpectation,
        auto_apply_enabled: autoApplyEnabled,
        auto_apply_consent: autoApplyConsent,
        require_approval_before_apply: requireApprovalBeforeApply,
        companies_to_avoid: companiesToAvoid,
        max_applications_per_day: Number(maxApplicationsPerDay || "10"),
        minimum_match_score: Number(minimumMatchScore || "80"),
        application_summary: applicationSummary
      };
      const res = await authFetch(`${backendUrl}/api/profile/upsert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Could not save profile.");
      setMessage("Profile saved.");
    } catch (err) {
      const text = err instanceof Error ? err.message : "Profile update failed.";
      if (text === "Failed to fetch") {
        setMessage(
          "Failed to fetch backend. Check NEXT_PUBLIC_BACKEND_URL and Render CORS settings."
        );
        return;
      }
      setMessage(text);
    }
  }

  async function runMatch(): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    if (!resumeFile) return;
    setMessage("Matching jobs...");
    setResults([]);
    try {
      const formData = new FormData();
      formData.set("resume_file", resumeFile);
      formData.set("role", "custom");
      formData.set("custom_role", targetRole);
      formData.set("top_k", "20");
      formData.set("min_score", "1.5");

      const res = await authFetch(`${backendUrl}/api/rag/match`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Match request failed.");
      setResults(data.results ?? []);
      setMessage(`Found ${data.count ?? 0} matching jobs.`);
    } catch (err) {
      const text = err instanceof Error ? err.message : "Failed to match jobs.";
      if (text === "Failed to fetch") {
        setMessage(
          "Failed to fetch backend. Check NEXT_PUBLIC_BACKEND_URL and Render CORS settings."
        );
        return;
      }
      setMessage(text);
    }
  }

  async function runAutoApply(): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    if (!autoApplyEnabled || !autoApplyConsent) {
      setMessage("Enable Auto Apply and consent before running auto apply.");
      return;
    }
    try {
      const res = await authFetch(`${backendUrl}/api/auto-apply/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "custom", custom_role: targetRole, max_jobs: 10 })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Auto Apply failed.");
      setMessage(
        `Auto Apply completed. Matched ${data.matched_jobs}, queued ${data.queued_applications}.`
      );
    } catch (err) {
      const text = err instanceof Error ? err.message : "Auto Apply failed.";
      setMessage(text);
    }
  }

  async function startCheckout(): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    if (!priceId) {
      setMessage("Missing NEXT_PUBLIC_STRIPE_PRICE_ID in frontend env.");
      return;
    }
    try {
      const body = {
        price_id: priceId,
        success_url: `${window.location.origin}/dashboard?payment=success`,
        cancel_url: `${window.location.origin}/dashboard?payment=cancel`,
        mode: "subscription"
      };
      const res = await authFetch(`${backendUrl}/api/payments/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Checkout request failed.");
      window.location.href = data.checkout_url;
    } catch (err) {
      const text = err instanceof Error ? err.message : "Payment failed.";
      if (text === "Failed to fetch") {
        setMessage(
          "Failed to fetch backend. Check NEXT_PUBLIC_BACKEND_URL and Render CORS settings."
        );
        return;
      }
      setMessage(text);
    }
  }

  async function signOut(): Promise<void> {
    await supabase.auth.signOut();
    router.push("/");
  }

  if (loading) {
    return (
      <main className="dash-shell">
        <p>Loading...</p>
      </main>
    );
  }

  return (
    <main className="dash-shell">
      <header className="dash-header">
        <div>
          <p className="brand">AIapply.ai Dashboard</p>
          <h1>{userEmail}</h1>
        </div>
        <button onClick={signOut} className="ghost">
          Sign Out
        </button>
      </header>

      <section className="panel">
        <h2>Profile and Application Preferences</h2>
        <div className="grid two">
          <label>
            Full Name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </label>
          <label>
            Target Role
            <input
              list="role-suggestions"
              value={targetRole}
              onChange={(e) => {
                setTargetRole(e.target.value);
                void fetchRoleSuggestions(e.target.value);
              }}
              placeholder="e.g. Software Engineer, Nurse, Data Analyst"
            />
            <datalist id="role-suggestions">
              {roleSuggestions.map((role) => (
                <option key={role} value={role} />
              ))}
            </datalist>
          </label>
          <label>
            Experience Level
            <input
              placeholder="e.g. Entry-level, 3 years, Senior"
              value={experienceLevel}
              onChange={(e) => setExperienceLevel(e.target.value)}
            />
          </label>
          <label>
            Skills (comma separated)
            <input
              placeholder="Python, FastAPI, React, ICU, EMR"
              value={skillsText}
              onChange={(e) => setSkillsText(e.target.value)}
            />
          </label>
          <label>
            Phone
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <label>
            Location
            <input value={location} onChange={(e) => setLocation(e.target.value)} />
          </label>
          <label>
            LinkedIn URL
            <input value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} />
          </label>
          <label>
            Portfolio URL
            <input value={portfolioUrl} onChange={(e) => setPortfolioUrl(e.target.value)} />
          </label>
          <label>
            Work Authorization
            <input
              placeholder="US Citizen, Green Card, Visa..."
              value={workAuthorizationStatus}
              onChange={(e) => setWorkAuthorizationStatus(e.target.value)}
            />
          </label>
          <label>
            Preferred Locations
            <input
              placeholder="Remote, New York, Austin..."
              value={preferredLocations}
              onChange={(e) => setPreferredLocations(e.target.value)}
            />
          </label>
          <label>
            Work Preferences
            <input
              placeholder="Remote, Hybrid, On-site"
              value={workPreferences}
              onChange={(e) => setWorkPreferences(e.target.value)}
            />
          </label>
          <label>
            Salary Expectation (optional)
            <input
              placeholder="$120k-$150k"
              value={salaryExpectation}
              onChange={(e) => setSalaryExpectation(e.target.value)}
            />
          </label>
          <label>
            Veteran Status (optional)
            <input value={veteranStatus} onChange={(e) => setVeteranStatus(e.target.value)} />
          </label>
          <label>
            Race/Ethnicity (optional)
            <input value={raceEthnicity} onChange={(e) => setRaceEthnicity(e.target.value)} />
          </label>
          <label>
            Gender Identity (optional)
            <input value={genderIdentity} onChange={(e) => setGenderIdentity(e.target.value)} />
          </label>
          <label>
            Disability Status (optional)
            <input value={disabilityStatus} onChange={(e) => setDisabilityStatus(e.target.value)} />
          </label>
          <label>
            Application Summary
            <input
              placeholder="Short summary used for applications"
              value={applicationSummary}
              onChange={(e) => setApplicationSummary(e.target.value)}
            />
          </label>
          <label>
            Need Sponsorship
            <input
              type="checkbox"
              checked={needsSponsorship}
              onChange={(e) => setNeedsSponsorship(e.target.checked)}
            />
          </label>
          <label>
            Willing to Relocate
            <input
              type="checkbox"
              checked={willingToRelocate}
              onChange={(e) => setWillingToRelocate(e.target.checked)}
            />
          </label>
          <label>
            Enable Auto Apply
            <input
              type="checkbox"
              checked={autoApplyEnabled}
              onChange={(e) => setAutoApplyEnabled(e.target.checked)}
            />
          </label>
          <label>
            Consent to Use Profile Data for Auto Apply
            <input
              type="checkbox"
              checked={autoApplyConsent}
              onChange={(e) => setAutoApplyConsent(e.target.checked)}
            />
          </label>
          <label>
            Require Approval Before Apply
            <input
              type="checkbox"
              checked={requireApprovalBeforeApply}
              onChange={(e) => setRequireApprovalBeforeApply(e.target.checked)}
            />
          </label>
          <label>
            Companies to Avoid
            <input
              placeholder="Company A, Company B"
              value={companiesToAvoid}
              onChange={(e) => setCompaniesToAvoid(e.target.value)}
            />
          </label>
          <label>
            Max Applications Per Day
            <input
              type="number"
              min="1"
              max="50"
              value={maxApplicationsPerDay}
              onChange={(e) => setMaxApplicationsPerDay(e.target.value)}
            />
          </label>
          <label>
            Minimum Match Score
            <input
              type="number"
              min="0"
              max="100"
              value={minimumMatchScore}
              onChange={(e) => setMinimumMatchScore(e.target.value)}
            />
          </label>
        </div>
        <button onClick={saveProfile}>Save Profile</button>
      </section>

      <section className="panel">
        <h2>Resume Match (RAG)</h2>
        <div className="grid">
          <label>
            Upload Resume
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        <button onClick={runMatch} disabled={!canRunMatch}>
          Match Jobs
        </button>
      </section>

      <section className="panel">
        <h2>Auto Apply</h2>
        <p>
          Auto Apply uses your saved profile and explicit consent settings to queue supported
          applications.
        </p>
        <button onClick={runAutoApply}>Run Auto Apply</button>
      </section>

      <section className="panel">
        <h2>Upgrade</h2>
        <p>Purchase Pro to unlock unlimited matching and premium automations.</p>
        <button onClick={startCheckout}>Buy Pro</button>
      </section>

      {message && <p className="status">{message}</p>}

      <section className="results-grid">
        {results.map((job) => (
          <article key={job.url} className="job-card">
            <h3>{job.title}</h3>
            <p>{job.company} | {job.location}</p>
            <p>
              RAG: {job.rag_score}/5 | Final: {job.final_score}/5
            </p>
            <p>{job.explanation}</p>
            <a href={job.url} target="_blank" rel="noreferrer">
              Open Job
            </a>
          </article>
        ))}
      </section>
    </main>
  );
}
