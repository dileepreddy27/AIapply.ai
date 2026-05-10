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
  ats_score: number;
  overlap_terms: string[];
  explanation: string;
};

type SubProfile = {
  id: string;
  name: string;
  target_role: string;
  target_sector: string;
  preferred_locations: string;
  work_preferences: string[];
  companies_to_avoid: string;
  minimum_match_score: number;
  kpi_focus: string;
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
  work_authorization_statuses: string[];
  veteran_statuses: string[];
  race_ethnicity_options: string[];
  gender_identity_options: string[];
  disability_status_options: string[];
  work_preference_options: string[];
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

type SubscriptionFeatures = {
  can_job_match: boolean;
  can_auto_apply: boolean;
  can_run_continuous_auto_apply: boolean;
  can_use_assistant: boolean;
  max_auto_apply_per_day: number;
  assistant_modes: string[];
  highlights: string[];
};

type SubscriptionState = {
  plan: "basic" | "pro";
  label: string;
  status: string;
  testing_mode?: boolean;
  assistant_prompts_used: number;
  assistant_prompts_limit: number | null;
  assistant_prompts_remaining: number | null;
  features: SubscriptionFeatures;
};

type CompetitiveAdvantage = {
  title: string;
  description: string;
};

type AssistantModeOption = {
  value: string;
  label: string;
};

type AssistantThread = {
  id: number;
  title: string;
  mode: string;
  updated_at: string;
};

type AssistantMessage = {
  id: number;
  thread_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
};

type DashboardStep = "profile" | "matched_jobs" | "auto_apply" | "analytics";

function cleanPriceId(raw: string): string {
  return raw
    .replace(/\\n/g, "")
    .replace(/[\n\r\t]/g, "")
    .replace(/\\/g, "")
    .replace(/"/g, "")
    .replace(/'/g, "")
    .trim();
}

function defaultSubscription(): SubscriptionState {
  return {
    plan: "basic",
    label: "Basic",
    status: "inactive",
    testing_mode: false,
    assistant_prompts_used: 0,
    assistant_prompts_limit: 20,
    assistant_prompts_remaining: 20,
    features: {
      can_job_match: true,
      can_auto_apply: false,
      can_run_continuous_auto_apply: false,
      can_use_assistant: true,
      max_auto_apply_per_day: 0,
      assistant_modes: [],
      highlights: []
    }
  };
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
  const [requireApprovalBeforeApply, setRequireApprovalBeforeApply] = useState(false);
  const [workPreferences, setWorkPreferences] = useState("");
  const [companyRankingFilter, setCompanyRankingFilter] = useState("any");
  const [companiesToAvoid, setCompaniesToAvoid] = useState("");
  const [maxApplicationsPerDay, setMaxApplicationsPerDay] = useState("10");
  const [minimumMatchScore, setMinimumMatchScore] = useState("80");
  const [subProfiles, setSubProfiles] = useState<SubProfile[]>([]);
  const [activeSubProfileId, setActiveSubProfileId] = useState("");
  const [subProfileName, setSubProfileName] = useState("");
  const [subProfileKpiFocus, setSubProfileKpiFocus] = useState("");

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [results, setResults] = useState<MatchResult[]>([]);
  const [roleSuggestions, setRoleSuggestions] = useState<string[]>([]);
  const [roleInputDirty, setRoleInputDirty] = useState(false);
  const [profileOptions, setProfileOptions] = useState<ProfileOptions>({
    job_sectors: [],
    countries: [],
    company_ranking_filters: [],
    work_authorization_statuses: [],
    veteran_statuses: [],
    race_ethnicity_options: [],
    gender_identity_options: [],
    disability_status_options: [],
    work_preference_options: []
  });
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [applicationsCount, setApplicationsCount] = useState(0);
  const [subscription, setSubscription] = useState<SubscriptionState>(defaultSubscription());
  const [competitiveAdvantages, setCompetitiveAdvantages] = useState<CompetitiveAdvantage[]>([]);
  const [assistantModes, setAssistantModes] = useState<AssistantModeOption[]>([]);
  const [assistantMode, setAssistantMode] = useState("job_search_planning");
  const [assistantDraft, setAssistantDraft] = useState("");
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantThread, setAssistantThread] = useState<AssistantThread | null>(null);
  const [assistantMessages, setAssistantMessages] = useState<AssistantMessage[]>([]);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantError, setAssistantError] = useState("");
  const [showApplications, setShowApplications] = useState(false);
  const [activeStep, setActiveStep] = useState<DashboardStep>("profile");

  const selectedCountry = useMemo(
    () => profileOptions.countries.find((entry) => entry.label === country),
    [country, profileOptions.countries]
  );
  const availableRegions = selectedCountry?.regions ?? [];
  const testingPremiumMode = subscription.testing_mode || subscription.status === "testing";
  const autoApplyLocked = !testingPremiumMode && !subscription.features.can_auto_apply;
  const recentApplications = useMemo(() => applications.slice(0, 6), [applications]);
  const topResults = useMemo(() => results.slice(0, 6), [results]);
  const sourceMix = useMemo(() => {
    const counts = new Map<string, number>();
    results.forEach((item) => {
      counts.set(item.source, (counts.get(item.source) ?? 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [results]);
  const averageMatchScore = useMemo(() => {
    if (!results.length) return 0;
    const total = results.reduce((sum, item) => sum + Number(item.final_score || 0), 0);
    return Number((total / results.length).toFixed(2));
  }, [results]);
  const queuePendingCount = useMemo(
    () => applications.filter((item) => item.status === "approval_required").length,
    [applications]
  );
  const queueReadyCount = useMemo(
    () => applications.filter((item) => item.status === "queued_auto_apply").length,
    [applications]
  );
  const profileCompletion = useMemo(() => {
    const checks = [
      fullName,
      targetRole,
      experienceLevel,
      skillsText,
      targetSector,
      country,
      preferredLocations,
      workPreferences,
      workAuthorizationStatus,
      salaryExpectation,
      applicationSummary,
      linkedinUrl || portfolioUrl
    ];
    const filled = checks.filter((value) => String(value || "").trim().length > 0).length;
    return Math.round((filled / checks.length) * 100);
  }, [
    applicationSummary,
    country,
    experienceLevel,
    fullName,
    linkedinUrl,
    portfolioUrl,
    preferredLocations,
    salaryExpectation,
    skillsText,
    targetRole,
    targetSector,
    workAuthorizationStatus,
    workPreferences
  ]);
  const assistantUsageLabel = testingPremiumMode
    ? "Premium features enabled for testing"
    : subscription.assistant_prompts_limit === null
      ? "Unlimited prompts"
      : `${subscription.assistant_prompts_remaining ?? 0} prompts left`;

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
        loadSubscription(session.access_token),
        loadProfileOptions(session.access_token),
        loadProfile(session.access_token),
        loadApplications(session.access_token),
        loadAssistantState(session.access_token)
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


  useEffect(() => {
    if (!assistantModes.length) return;
    if (!assistantModes.some((mode) => mode.value === assistantMode)) {
      setAssistantMode(assistantModes[0].value);
    }
  }, [assistantMode, assistantModes]);

  useEffect(() => {
    const active = subProfiles.find((item) => item.id === activeSubProfileId);
    if (!active) return;
    setSubProfileName(active.name);
    setSubProfileKpiFocus(active.kpi_focus);
  }, [activeSubProfileId, subProfiles]);

  useEffect(() => {
    const targetMap: Record<DashboardStep, string> = {
      profile: "profile",
      matched_jobs: "results",
      auto_apply: "automation",
      analytics: "analytics"
    };
    const element = document.getElementById(targetMap[activeStep]);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [activeStep]);

  function isBackendConfigured(): boolean {
    return !!backendUrl && /^https?:\/\//.test(backendUrl);
  }

  function backendConfigMessage(): string {
    return "Backend URL is not configured. Set NEXT_PUBLIC_BACKEND_URL in Vercel env and redeploy.";
  }

  function humanizeAssistantError(text: string): string {
    const normalized = text.toLowerCase();
    if (normalized.includes("incorrect api key") || normalized.includes("invalid_api_key") || normalized.includes("openai api key is invalid")) {
      return "Your OpenAI key is invalid in Render. Update OPENAI_API_KEY, keep ASSISTANT_PROVIDER=openai, redeploy Render, and reopen the assistant.";
    }
    if (normalized.includes("insufficient balance") || normalized.includes("balance is empty")) {
      return "The assistant account does not have available API credit right now. Add billing to the active OpenAI account in Render, redeploy if needed, and try again.";
    }
    if (normalized.includes("quota") || normalized.includes("rate limit")) {
      return "The OpenAI assistant hit a quota or rate-limit issue. Check OpenAI billing and usage for the key configured in Render, then try again.";
    }
    return text;
  }

  function syncFromSubProfile(profile: SubProfile): void {
    setActiveSubProfileId(profile.id);
    setSubProfileName(profile.name);
    setSubProfileKpiFocus(profile.kpi_focus);
    if (profile.target_role) setTargetRole(profile.target_role);
    if (profile.target_sector) setTargetSector(profile.target_sector);
    if (profile.preferred_locations) setPreferredLocations(profile.preferred_locations);
    if (profile.work_preferences.length) setWorkPreferences(profile.work_preferences.join(", "));
    if (profile.companies_to_avoid) setCompaniesToAvoid(profile.companies_to_avoid);
    if (profile.minimum_match_score) setMinimumMatchScore(String(profile.minimum_match_score));
  }

  function saveCurrentAsSubProfile(): void {
    const identifier = activeSubProfileId || `sub-${Date.now()}`;
    const next: SubProfile = {
      id: identifier,
      name: subProfileName.trim() || targetRole.trim() || `Profile ${subProfiles.length + 1}`,
      target_role: targetRole.trim(),
      target_sector: targetSector.trim(),
      preferred_locations: preferredLocations.trim(),
      work_preferences: workPreferences
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      companies_to_avoid: companiesToAvoid.trim(),
      minimum_match_score: Number(minimumMatchScore || "80"),
      kpi_focus: subProfileKpiFocus.trim()
    };
    setSubProfiles((current) => {
      const withoutExisting = current.filter((item) => item.id !== identifier);
      return [next, ...withoutExisting].slice(0, 8);
    });
    setActiveSubProfileId(identifier);
    setMessage(`Saved sub profile: ${next.name}`);
  }

  function removeSubProfile(id: string): void {
    setSubProfiles((current) => current.filter((item) => item.id !== id));
    if (activeSubProfileId === id) {
      setActiveSubProfileId("");
      setSubProfileName("");
      setSubProfileKpiFocus("");
    }
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
          : [],
        work_authorization_statuses: Array.isArray(data?.work_authorization_statuses)
          ? data.work_authorization_statuses
          : [],
        veteran_statuses: Array.isArray(data?.veteran_statuses) ? data.veteran_statuses : [],
        race_ethnicity_options: Array.isArray(data?.race_ethnicity_options)
          ? data.race_ethnicity_options
          : [],
        gender_identity_options: Array.isArray(data?.gender_identity_options)
          ? data.gender_identity_options
          : [],
        disability_status_options: Array.isArray(data?.disability_status_options)
          ? data.disability_status_options
          : [],
        work_preference_options: Array.isArray(data?.work_preference_options)
          ? data.work_preference_options
          : []
      });
      setAssistantModes(Array.isArray(data?.assistant_modes) ? data.assistant_modes : []);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadSubscription(accessToken: string = token): Promise<void> {
    try {
      const res = await fetch(`${backendUrl}/api/subscription/me`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      const data = await res.json();
      if (data?.subscription) {
        setSubscription(data.subscription);
      }
      setCompetitiveAdvantages(
        Array.isArray(data?.competitive_advantages) ? data.competitive_advantages : []
      );
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
      if (data?.subscription) {
        setSubscription(data.subscription);
      }
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
      const storedAutoApplyEnabled = Boolean(app.auto_apply_enabled);
      setAutoApplyEnabled(storedAutoApplyEnabled);
      setAutoApplyConsent(storedAutoApplyEnabled ? Boolean(app.auto_apply_consent) : false);
      setRequireApprovalBeforeApply(storedAutoApplyEnabled ? Boolean(app.require_approval_before_apply) : false);
      setWorkPreferences((app.work_preferences || []).join(", "));
      setCompanyRankingFilter(app.company_ranking_filter ?? "any");
      setCompaniesToAvoid(app.companies_to_avoid ?? "");
      setMaxApplicationsPerDay(String(app.max_applications_per_day ?? 10));
      setMinimumMatchScore(String(app.minimum_match_score ?? 80));
      setSubProfiles(Array.isArray(app.sub_profiles) ? app.sub_profiles : []);
      setActiveSubProfileId(app.active_sub_profile_id ?? "");
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

  async function loadAssistantState(accessToken: string = token): Promise<void> {
    if (!isBackendConfigured()) return;
    try {
      const res = await fetch(`${backendUrl}/api/assistant/me`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      const data = await res.json();
      if (data?.subscription) {
        setSubscription(data.subscription);
      }
      setAssistantModes(Array.isArray(data?.modes) ? data.modes : []);
      setAssistantThread(data?.active_thread ?? null);
      setAssistantMessages(Array.isArray(data?.messages) ? data.messages : []);
      if (data?.active_thread?.mode) {
        setAssistantMode(data.active_thread.mode);
      }
      setAssistantError("");
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
        auto_apply_consent: autoApplyEnabled ? autoApplyConsent : false,
        require_approval_before_apply: autoApplyEnabled ? requireApprovalBeforeApply : false,
        company_ranking_filter: companyRankingFilter,
        companies_to_avoid: companiesToAvoid,
        max_applications_per_day: Number(maxApplicationsPerDay || "10"),
        minimum_match_score: Number(minimumMatchScore || "80"),
        application_summary: applicationSummary,
        sub_profiles: subProfiles,
        active_sub_profile_id: activeSubProfileId
      };
      const res = await authFetch(`${backendUrl}/api/profile/upsert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Could not save profile.");
      if (data?.subscription) {
        setSubscription(data.subscription);
      }
      setActiveStep("matched_jobs");
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
      setActiveStep("matched_jobs");
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
    if (autoApplyLocked) {
      setMessage("Auto Apply is still locked by plan settings. Turn on testing unlock or switch this account to Pro.");
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
      await loadSubscription();
      setShowApplications(true);
      setActiveStep("analytics");
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
    if (subscription.plan === "pro" && subscription.status !== "inactive") {
      setMessage("This account already has Pro access.");
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

  async function sendAssistantMessage(): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    if (!subscription.features.can_use_assistant) {
      const detail = "Your plan does not include the Personal Assistant Agent.";
      setAssistantError(detail);
      setMessage(detail);
      return;
    }
    if (!assistantDraft.trim()) {
      const detail = "Enter a message for the Personal Assistant.";
      setAssistantError(detail);
      setMessage(detail);
      return;
    }

    setAssistantLoading(true);
    setAssistantError("");
    try {
      const res = await authFetch(`${backendUrl}/api/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: assistantMode,
          message: assistantDraft,
          thread_id: assistantThread?.id ?? null
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Assistant request failed.");
      if (data?.subscription) {
        setSubscription(data.subscription);
      }
      setAssistantMessages(Array.isArray(data?.messages) ? data.messages : []);
      if (data?.thread_id) {
        setAssistantThread((prev) => ({
          id: Number(data.thread_id),
          title: prev?.title ?? "Career Assistant",
          mode: assistantMode,
          updated_at: new Date().toISOString()
        }));
      }
      setAssistantDraft("");
      setAssistantError("");
      setMessage("Personal Assistant response ready.");
    } catch (err) {
      const text = err instanceof Error ? err.message : "Assistant request failed.";
      const detail = humanizeAssistantError(text);
      setAssistantError(detail);
      setMessage(detail);
    } finally {
      setAssistantLoading(false);
    }
  }

  function resetAssistantConversation(): void {
    setAssistantThread(null);
    setAssistantMessages([]);
    setAssistantDraft("");
    setAssistantError("");
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
    <main className="app-shell">
      <aside className="dashboard-sidebar">
        <div className="sidebar-brand">
          <p className="brand">AIapply.ai</p>
          <h1>Control Room</h1>
          <p className="sidebar-copy">One workspace for matching, automation, and assistant support.</p>
        </div>

        <nav className="sidebar-nav" aria-label="Dashboard sections">
          <button type="button" className={`sidebar-link${activeStep === "profile" ? " active" : ""}`} onClick={() => setActiveStep("profile")}>Profile</button>
          <button type="button" className={`sidebar-link${activeStep === "matched_jobs" ? " active" : ""}`} onClick={() => setActiveStep("matched_jobs")}>Matched Jobs</button>
          <button type="button" className={`sidebar-link${activeStep === "auto_apply" ? " active" : ""}`} onClick={() => setActiveStep("auto_apply")}>Auto Apply</button>
          <button type="button" className={`sidebar-link${activeStep === "analytics" ? " active" : ""}`} onClick={() => setActiveStep("analytics")}>Analytics</button>
        </nav>

        <div className="sidebar-plan-card">
          <span className={`plan-pill ${subscription.plan}`}>{subscription.label}</span>
          <h3>{assistantUsageLabel}</h3>
          <p>Status: {testingPremiumMode ? "testing unlock active" : subscription.status.replace(/_/g, " ")}</p>
          <p className="field-hint">Testing mode is active, so Auto Apply and assistant workflows stay visible while we validate the product flow.</p>
        </div>

        <button onClick={signOut} className="ghost sidebar-signout">
          Sign Out
        </button>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-topbar">
          <div>
            <p className="brand">Career Intelligence Dashboard</p>
            <h2>{fullName || userEmail}</h2>
            <p className="status-inline">
              Resume-first matching, controlled automation, and a corner assistant for fast help.
            </p>
          </div>
          <div className="dashboard-topbar-meta">
            <span className="topbar-chip">{subProfileName || targetRole || "Target role pending"}</span>
            <span className="topbar-chip">{testingPremiumMode ? "Testing unlock active" : (country || "Global search")}</span>
          </div>
        </header>

        {message && <div className="status-banner">{message}</div>}

        <section className="metric-grid" id="analytics">
          <article className="metric-card">
            <p className="metric-label">Profile Completion</p>
            <strong>{profileCompletion}%</strong>
            <span>Fields ready for matching and apply flows</span>
          </article>
          <article className="metric-card">
            <p className="metric-label">Matched Jobs</p>
            <strong>{results.length}</strong>
            <span>Average score {averageMatchScore}/5</span>
          </article>
          <article className="metric-card">
            <p className="metric-label">Total Jobs Applied</p>
            <strong>{applicationsCount}</strong>
            <span>{queuePendingCount} waiting review · {queueReadyCount} ready</span>
          </article>
          <article className="metric-card">
            <p className="metric-label">Assistant Access</p>
            <strong>{subscription.label}</strong>
            <span>{assistantUsageLabel}</span>
          </article>
        </section>

        <section className="workflow-strip">
          <button type="button" className={`workflow-chip${activeStep === "profile" ? " active" : ""}`} onClick={() => setActiveStep("profile")}>1. Profile</button>
          <button type="button" className={`workflow-chip${activeStep === "matched_jobs" ? " active" : ""}`} onClick={() => setActiveStep("matched_jobs")}>2. Matching Jobs</button>
          <button type="button" className={`workflow-chip${activeStep === "auto_apply" ? " active" : ""}`} onClick={() => setActiveStep("auto_apply")}>3. Auto Apply</button>
          <button type="button" className={`workflow-chip${activeStep === "analytics" ? " active" : ""}`} onClick={() => setActiveStep("analytics")}>4. Analytics</button>
        </section>

        <section className="dashboard-grid">
          <article
            className="dashboard-card dashboard-card-wide"
            id="profile"
            style={activeStep === "profile" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Search Strategy</p>
                <h3>Targeting Console</h3>
              </div>
              <div className="inline-actions">
                <button onClick={saveProfile}>Save Profile</button>
                <button onClick={runMatch} disabled={!canRunMatch}>
                  Match Jobs
                </button>
              </div>
            </div>
            <div className="dashboard-form-grid">
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
              <label className="dashboard-field-wide">
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
                  Smart suggestions react to what the user types instead of forcing a fixed dropdown.
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
                Preferred Locations
                <input
                  placeholder="Remote, New York, Austin..."
                  value={preferredLocations}
                  onChange={(e) => setPreferredLocations(e.target.value)}
                />
              </label>
              <label>
                Work Preferences
                <select value={workPreferences} onChange={(e) => setWorkPreferences(e.target.value)}>
                  <option value="">Select work preference</option>
                  {profileOptions.work_preference_options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
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
                Upload Resume
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
                />
                <span className="field-hint">{resumeFile ? resumeFile.name : "No file selected yet."}</span>
              </label>
            </div>
          </article>

          <article
            className="dashboard-card"
            style={activeStep === "profile" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Profile</p>
                <h3>Candidate Snapshot</h3>
              </div>
            </div>
            <div className="dashboard-form-grid">
              <label>
                Full Name
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </label>
              <label>
                Experience Level
                <input
                  placeholder="Entry-level, 3 years, Senior"
                  value={experienceLevel}
                  onChange={(e) => setExperienceLevel(e.target.value)}
                />
              </label>
              <label className="dashboard-field-wide">
                Skills
                <textarea
                  rows={4}
                  placeholder="Python, FastAPI, React, ICU, EMR"
                  value={skillsText}
                  onChange={(e) => setSkillsText(e.target.value)}
                />
              </label>
              <label>
                LinkedIn URL
                <input value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} />
              </label>
              <label>
                Portfolio URL
                <input value={portfolioUrl} onChange={(e) => setPortfolioUrl(e.target.value)} />
              </label>
              <label className="dashboard-field-wide">
                Application Summary
                <textarea
                  rows={4}
                  placeholder="Short summary used for applications"
                  value={applicationSummary}
                  onChange={(e) => setApplicationSummary(e.target.value)}
                />
              </label>
            </div>
          </article>

          <article
            className="dashboard-card"
            style={activeStep === "profile" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Multi Role Strategy</p>
                <h3>Sub Profiles</h3>
              </div>
              <button type="button" onClick={saveCurrentAsSubProfile} className="ghost">
                Save Current Role
              </button>
            </div>
            <div className="dashboard-form-grid">
              <label>
                Sub Profile Name
                <input
                  value={subProfileName}
                  onChange={(e) => setSubProfileName(e.target.value)}
                  placeholder="Frontend Focus, AI Automation, Backend Core"
                />
              </label>
              <label>
                KPI / Role Goal
                <input
                  value={subProfileKpiFocus}
                  onChange={(e) => setSubProfileKpiFocus(e.target.value)}
                  placeholder="React roles in remote US, 5 applications daily"
                />
              </label>
            </div>
            <div className="sub-profile-list">
              {subProfiles.length === 0 ? (
                <p className="empty-state">
                  Save multiple role strategies here for frontend, backend, full stack, AI automation, and more.
                </p>
              ) : (
                subProfiles.map((item) => (
                  <article
                    key={item.id}
                    className={`sub-profile-card${item.id === activeSubProfileId ? " active" : ""}`}
                  >
                    <div>
                      <h4>{item.name}</h4>
                      <p>{item.target_role || "Untitled role"} · {item.preferred_locations || "Any location"}</p>
                      {item.kpi_focus && <p>{item.kpi_focus}</p>}
                    </div>
                    <div className="feature-actions">
                      <button type="button" className="ghost" onClick={() => syncFromSubProfile(item)}>
                        Use
                      </button>
                      <button type="button" className="ghost" onClick={() => removeSubProfile(item.id)}>
                        Remove
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </article>

          <article
            className="dashboard-card"
            id="automation"
            style={activeStep === "auto_apply" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Automation</p>
                <h3>Automation Rules</h3>
              </div>
              <button onClick={runAutoApply}>
                Run Auto Apply
              </button>
            </div>
            <p className="field-hint">
              Live discovery uses Greenhouse and Lever directly, and also supports LinkedIn, Indeed,
              and other portal imports from the backend `data/imports` folder.
            </p>
            <div className="dashboard-form-grid">
              <label>
                Work Authorization
                <select
                  value={workAuthorizationStatus}
                  onChange={(e) => setWorkAuthorizationStatus(e.target.value)}
                >
                  <option value="">Select work authorization / visa status</option>
                  {profileOptions.work_authorization_statuses.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>
                Salary Expectation
                <input
                  placeholder="$120k-$150k"
                  value={salaryExpectation}
                  onChange={(e) => setSalaryExpectation(e.target.value)}
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
              <label>
                Location
                <input value={location} onChange={(e) => setLocation(e.target.value)} />
              </label>
            </div>
            <div className="toggle-grid">
              <label className="toggle-card">
                <span>Need Sponsorship</span>
                <input
                  type="checkbox"
                  checked={needsSponsorship}
                  onChange={(e) => setNeedsSponsorship(e.target.checked)}
                />
              </label>
              <label className="toggle-card">
                <span>Willing to Relocate</span>
                <input
                  type="checkbox"
                  checked={willingToRelocate}
                  onChange={(e) => setWillingToRelocate(e.target.checked)}
                />
              </label>
              <label className="toggle-card">
                <span>Enable Auto Apply</span>
                <input
                  type="checkbox"
                  checked={autoApplyEnabled}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setAutoApplyEnabled(checked);
                    if (!checked) {
                      setAutoApplyConsent(false);
                      setRequireApprovalBeforeApply(false);
                    }
                  }}
                />
              </label>
              <label className="toggle-card">
                <span>Consent to Use Profile Data</span>
                <input
                  type="checkbox"
                  checked={autoApplyConsent}
                  onChange={(e) => setAutoApplyConsent(e.target.checked)}
                />
              </label>
              <label className="toggle-card">
                <span>Require Approval Before Apply</span>
                <input
                  type="checkbox"
                  checked={requireApprovalBeforeApply}
                  onChange={(e) => setRequireApprovalBeforeApply(e.target.checked)}
                />
              </label>
            </div>
          </article>

          <article
            className="dashboard-card dashboard-card-wide"
            id="results"
            style={activeStep === "matched_jobs" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Matched Jobs</p>
                <h3>Opportunity Feed</h3>
              </div>
              <span className="status-inline">
                {results.length ? `${results.length} jobs surfaced` : "Upload a resume and run matching"}
              </span>
            </div>
            <div className="results-stack">
              {topResults.length === 0 ? (
                <p className="empty-state">
                  No matched jobs yet. Save your targeting profile, upload your resume, and run matching.
                </p>
              ) : (
                topResults.map((job) => (
                  <article key={job.url} className="job-row-card">
                    <div>
                      <h4>{job.title}</h4>
                      <p>{job.company} · {job.location} · {job.source}</p>
                      <p className="field-hint">{job.explanation}</p>
                    </div>
                    <div className="job-row-meta">
                      <span className="topbar-chip">ATS {job.ats_score}%</span>
                      <span className="topbar-chip">Final {job.final_score}/5</span>
                      <span className="status-inline">RAG {job.rag_score}/5</span>
                      <button type="button" className="ghost" onClick={() => setActiveStep("auto_apply")}>
                        Move To Auto Apply
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </article>

          <article
            className="dashboard-card"
            style={activeStep === "analytics" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Analytics</p>
                <h3>Pipeline + Source Mix</h3>
              </div>
              <button onClick={() => void loadApplications()} className="ghost" type="button">
                Refresh
              </button>
            </div>
            <div className="queue-stat-row">
              <span className="topbar-chip">{applicationsCount} applied</span>
              <span className="topbar-chip">{results.length} matched</span>
              <span className="topbar-chip">{profileCompletion}% profile</span>
            </div>
            <div className="queue-preview-list">
              {recentApplications.length === 0 ? (
                <p className="empty-state">No application records yet.</p>
              ) : (
                recentApplications.map((application) => (
                  <article key={application.id} className="queue-preview-card">
                    <div className="application-topline">
                      <h4>{application.title || "Untitled role"}</h4>
                      <span className={`status-pill ${application.status}`}>
                        {application.status.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p>{application.company || "Unknown company"} · {application.location || "Unknown location"}</p>
                    <p>{new Date(application.created_at).toLocaleString()}</p>
                  </article>
                ))
              )}
            </div>
            <ul className="plain-list">
              {sourceMix.map(([source, count]) => (
                <li key={source}>
                  <strong>{source}:</strong> {count} matched roles
                </li>
              ))}
            </ul>
          </article>

          <article
            className="dashboard-card"
            style={activeStep === "analytics" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Competitive Edge</p>
                <h3>What Makes This Stronger</h3>
              </div>
            </div>
            <ul className="plain-list">
              {competitiveAdvantages.map((item) => (
                <li key={item.title}>
                  <strong>{item.title}:</strong> {item.description}
                </li>
              ))}
            </ul>
          </article>

          <article
            className="dashboard-card"
            style={activeStep === "profile" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Compliance</p>
                <h3>Application Questions</h3>
              </div>
            </div>
            <div className="dashboard-form-grid">
              <label>
                Veteran Status (optional)
                <select value={veteranStatus} onChange={(e) => setVeteranStatus(e.target.value)}>
                  <option value="">Select veteran status</option>
                  {profileOptions.veteran_statuses.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>
                Race / Ethnicity (optional)
                <select value={raceEthnicity} onChange={(e) => setRaceEthnicity(e.target.value)}>
                  <option value="">Select race / ethnicity</option>
                  {profileOptions.race_ethnicity_options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>
                Gender Identity (optional)
                <select value={genderIdentity} onChange={(e) => setGenderIdentity(e.target.value)}>
                  <option value="">Select gender identity</option>
                  {profileOptions.gender_identity_options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>
                Disability Status (optional)
                <select value={disabilityStatus} onChange={(e) => setDisabilityStatus(e.target.value)}>
                  <option value="">Select disability status</option>
                  {profileOptions.disability_status_options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>
                Phone
                <input value={phone} onChange={(e) => setPhone(e.target.value)} />
              </label>
            </div>
          </article>
        </section>

        <button
          type="button"
          className="assistant-fab"
          onClick={() => setAssistantOpen((value) => !value)}
          aria-label="Open AIapply assistant"
        >
          <span className="assistant-fab-icon" aria-hidden="true">🤖</span>
        </button>

        {assistantOpen && (
          <aside className="assistant-drawer">
            <div className="assistant-drawer-header">
              <div>
                <p className="brand">AIapply Agent</p>
                <h2>Personal Assistant</h2>
                <p className="status-inline">
                  {testingPremiumMode
                    ? "Testing mode | premium assistant enabled"
                    : subscription.assistant_prompts_limit === null
                      ? `${subscription.label} plan | unlimited prompts`
                      : `${subscription.label} plan | ${subscription.assistant_prompts_remaining ?? 0} prompts left this month`}
                </p>
              </div>
              <button type="button" className="ghost" onClick={() => setAssistantOpen(false)}>
                Close
              </button>
            </div>

            <div className="grid">
              <label>
                Assistant Mode
                <select value={assistantMode} onChange={(e) => setAssistantMode(e.target.value)}>
                  {assistantModes.map((mode) => (
                    <option key={mode.value} value={mode.value}>
                      {mode.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {assistantError && <p className="assistant-error">{assistantError}</p>}

            <label className="assistant-composer">
              Ask the Assistant
              <textarea
                rows={5}
                value={assistantDraft}
                onChange={(e) => setAssistantDraft(e.target.value)}
                placeholder="Ask for resume edits, interview prep, follow-up email drafts, or a job-search plan."
              />
            </label>

            <div className="inline-actions">
              <button onClick={sendAssistantMessage} disabled={assistantLoading}>
                {assistantLoading ? "Thinking..." : "Ask Assistant"}
              </button>
              <button onClick={resetAssistantConversation} className="ghost" type="button">
                New Conversation
              </button>
            </div>

            <div className="assistant-list">
              {assistantMessages.length === 0 ? (
                <p className="empty-state">
                  No assistant messages yet. Start with planning, resume edits, or interview prep.
                </p>
              ) : (
                assistantMessages.map((item) => (
                  <article key={item.id} className={`assistant-card ${item.role}`}>
                    <div className="application-topline">
                      <h3>{item.role === "assistant" ? "AIapply Assistant" : "You"}</h3>
                      <span className="status-inline">
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="assistant-content">{item.content}</p>
                  </article>
                ))
              )}
            </div>
          </aside>
        )}
      </section>
    </main>
  );
}
