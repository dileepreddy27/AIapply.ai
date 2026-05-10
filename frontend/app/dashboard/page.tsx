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

type CountryOption = {
  label: string;
  regions: string[];
};

type CompanyRankingOption = {
  value: string;
  label: string;
};

type ProfileOptions = {
  job_sectors: string[];
  countries: CountryOption[];
  company_ranking_filters: CompanyRankingOption[];
};

type ApplicationRecord = {
  id: number;
  company: string;
  title: string;
  location: string;
  status: string;
  job_url: string;
  created_at: string;
  notes?: string;
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
  const [targetSector, setTargetSector] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [country, setCountry] = useState("");
  const [region, setRegion] = useState("");
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
  const [companyRankingFilter, setCompanyRankingFilter] = useState("any");
  const [companiesToAvoid, setCompaniesToAvoid] = useState("");
  const [maxApplicationsPerDay, setMaxApplicationsPerDay] = useState("10");
  const [minimumMatchScore, setMinimumMatchScore] = useState("80");

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [results, setResults] = useState<MatchResult[]>([]);
  const [roleSuggestions, setRoleSuggestions] = useState<string[]>([]);
  const [roleInputDirty, setRoleInputDirty] = useState(false);
  const [profileOptions, setProfileOptions] = useState<ProfileOptions>({
    job_sectors: [],
    countries: [],
    company_ranking_filters: []
  });
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [applicationsCount, setApplicationsCount] = useState(0);

  const selectedCountry = useMemo(
    () => profileOptions.countries.find((entry) => entry.label === country),
    [country, profileOptions.countries]
  );
  const availableRegions = selectedCountry?.regions ?? [];

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
        loadProfileOptions(session.access_token),
        loadProfile(session.access_token),
        loadApplications(session.access_token)
      ]);
    }
    bootstrap();
    return () => {
      mounted = false;
    };
  }, [router]);

  useEffect(() => {
    if (!token || !isBackendConfigured()) return;
    if (!roleInputDirty) return;
    const query = targetRole.trim();
    if (query.length < 2) {
      setRoleSuggestions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void fetchRoleSuggestions(query);
    }, 180);
    return () => window.clearTimeout(timer);
  }, [backendUrl, targetRole, targetSector, token]);

  useEffect(() => {
    if (!country) {
      setRegion("");
      return;
    }
    if (region && !availableRegions.includes(region)) {
      setRegion("");
    }
  }, [availableRegions, country, region]);

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
    if (query.trim().length < 2) {
      setRoleSuggestions([]);
      return;
    }
    try {
      const params = new URLSearchParams({ q: query });
      if (targetSector) {
        params.set("sector", targetSector);
      }
      const res = await fetch(
        `${backendUrl}/api/roles/search?${params.toString()}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      const data = await res.json();
      setRoleSuggestions(Array.isArray(data?.roles) ? data.roles : []);
    } catch {
      // silently ignore suggestions failures
    }
  }

  async function loadProfileOptions(accessToken: string): Promise<void> {
    try {
      const res = await fetch(`${backendUrl}/api/profile/options`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      const data = await res.json();
      setProfileOptions({
        job_sectors: Array.isArray(data?.job_sectors) ? data.job_sectors : [],
        countries: Array.isArray(data?.countries) ? data.countries : [],
        company_ranking_filters: Array.isArray(data?.company_ranking_filters)
          ? data.company_ranking_filters
          : []
      });
    } catch (err) {
      console.error(err);
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
      setTargetSector(app.target_sector ?? "");
      setPhone(app.phone ?? "");
      setLocation(app.location ?? "");
      setCountry(app.country ?? "");
      setRegion(app.region ?? "");
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
      setCompanyRankingFilter(app.company_ranking_filter ?? "any");
      setCompaniesToAvoid(app.companies_to_avoid ?? "");
      setMaxApplicationsPerDay(String(app.max_applications_per_day ?? 10));
      setMinimumMatchScore(String(app.minimum_match_score ?? 80));
    } catch (err) {
      console.error(err);
    }
  }

  async function loadApplications(accessToken: string = token): Promise<void> {
    if (!isBackendConfigured()) return;
    try {
      const res = await fetch(`${backendUrl}/api/applications/me`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      const data = await res.json();
      setApplications(Array.isArray(data?.applications) ? data.applications : []);
      setApplicationsCount(Number(data?.count ?? 0));
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
        target_sector: targetSector,
        phone,
        location,
        country,
        region,
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
        company_ranking_filter: companyRankingFilter,
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
      setMessage(
        data?.message ??
          `Found ${data.count ?? 0} matching jobs from ${data.scanned_jobs ?? 0} scanned openings.`
      );
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
      await loadApplications();
      setMessage(
        data?.message ??
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
            Job Sector
            <select value={targetSector} onChange={(e) => setTargetSector(e.target.value)}>
              <option value="">Any sector</option>
              {profileOptions.job_sectors.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </label>
          <label>
            Target Role
            <input
              value={targetRole}
              onChange={(e) => {
                setRoleInputDirty(true);
                setTargetRole(e.target.value);
              }}
              placeholder="Type keywords like python, backend, llm, nurse, data"
            />
            <span className="field-hint">
              Suggestions adapt to your keywords. You can also keep any custom role you type.
            </span>
            {roleSuggestions.length > 0 && (
              <div className="suggestion-list" role="listbox" aria-label="Target role suggestions">
                {roleSuggestions.map((role) => (
                  <button
                    key={role}
                    type="button"
                    className={`suggestion-chip${role === targetRole ? " selected" : ""}`}
                    onClick={() => {
                      setRoleInputDirty(true);
                      setTargetRole(role);
                      setRoleSuggestions([]);
                    }}
                  >
                    {role}
                  </button>
                ))}
              </div>
            )}
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
            Country
            <select
              value={country}
              onChange={(e) => {
                setCountry(e.target.value);
                setRegion("");
              }}
            >
              <option value="">Any country</option>
              {profileOptions.countries.map((entry) => (
                <option key={entry.label} value={entry.label}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            State / Province / Region
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              disabled={!country || availableRegions.length === 0}
            >
              <option value="">{country ? "Any region" : "Select country first"}</option>
              {availableRegions.map((entry) => (
                <option key={entry} value={entry}>
                  {entry}
                </option>
              ))}
            </select>
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
            Company Ranking Filter
            <select
              value={companyRankingFilter}
              onChange={(e) => setCompanyRankingFilter(e.target.value)}
            >
              {profileOptions.company_ranking_filters.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
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
        <div className="inline-actions">
          <button onClick={runAutoApply}>Run Auto Apply</button>
          <button onClick={() => void loadApplications()} className="ghost" type="button">
            Refresh Applications
          </button>
        </div>
        <div className="applications-meta">
          <strong>{applicationsCount}</strong> application records found for your account.
        </div>
        <div className="applications-list">
          {applications.length === 0 ? (
            <p className="empty-state">
              No application records yet. When Auto Apply queues jobs, they will appear here.
            </p>
          ) : (
            applications.map((application) => (
              <article key={application.id} className="application-card">
                <div className="application-topline">
                  <h3>{application.title || "Untitled role"}</h3>
                  <span className={`status-pill ${application.status}`}>
                    {application.status.replace(/_/g, " ")}
                  </span>
                </div>
                <p>
                  {application.company || "Unknown company"} | {application.location || "Unknown location"}
                </p>
                <p>{new Date(application.created_at).toLocaleString()}</p>
                {application.notes && <p>{application.notes}</p>}
                {application.job_url && (
                  <a href={application.job_url} target="_blank" rel="noreferrer">
                    Open Job
                  </a>
                )}
              </article>
            ))
          )}
        </div>
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
