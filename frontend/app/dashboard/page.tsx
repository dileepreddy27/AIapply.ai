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
  posted_at?: string;
  posted_relative?: string;
  posted_bucket?: string;
  posted_days_ago?: number | null;
};

type BookmarkEntry = {
  id: string;
  company: string;
  website: string;
  note?: string;
  created_at: string;
};

type DiscoverySourceCount = {
  source: string;
  token: string;
  jobs: number;
};

type DiscoveryDiagnostics = {
  imports_loaded: number;
  sources_checked: number;
  sources_succeeded: number;
  scanned_jobs?: number;
  query_filtered_jobs?: number;
  source_counts: DiscoverySourceCount[];
  source_errors: string[];
};


type PermissionRequest = {
  id: string;
  company: string;
  title: string;
  source_url: string;
  application_url: string;
  note?: string;
  created_at: string;
};

type AutoApplyQueueItem = {
  id: string;
  title: string;
  company: string;
  location: string;
  source: string;
  url: string;
  posted_relative?: string;
  final_score: number;
  ats_score: number;
  permission_required: boolean;
  application_url: string;
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

type TailoredDocument = {
  id: string;
  mode: "resume" | "cover_letter";
  company: string;
  job_title: string;
  tailored_text: string;
  changes: string[];
  keywords: string[];
  created_at: string;
};

const PIPELINE_STAGES: { key: string; label: string; statuses: string[] }[] = [
  { key: "queued", label: "Queued", statuses: ["approval_required", "queued_auto_apply"] },
  { key: "viewed", label: "Viewed", statuses: ["viewed"] },
  { key: "applied", label: "Applied", statuses: ["applied"] },
  { key: "replied", label: "Replied", statuses: ["replied"] },
  { key: "interviewing", label: "Interview", statuses: ["interviewing"] }
];

type SubscriptionFeatures = {
  can_job_match: boolean;
  can_auto_apply: boolean;
  can_run_continuous_auto_apply: boolean;
  can_use_assistant: boolean;
  max_auto_apply_per_day: number;
  monthly_application_limit?: number | null;
  assistant_modes: string[];
  highlights: string[];
};

type SubscriptionState = {
  plan: string;
  label: string;
  status: string;
  testing_mode?: boolean;
  price_usd?: number;
  assistant_prompts_used: number;
  assistant_prompts_limit: number | null;
  assistant_prompts_remaining: number | null;
  applications_used_this_month?: number;
  applications_monthly_limit?: number | null;
  applications_monthly_remaining?: number | null;
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

type PersistProfileOptions = {
  advanceStep?: DashboardStep | null;
  silent?: boolean;
  successMessage?: string | null;
};

type DashboardStep = "dashboard" | "profile" | "matched_jobs" | "bookmarks" | "auto_apply" | "analytics" | "tracker";

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
    applications_used_this_month: 0,
    applications_monthly_limit: 0,
    applications_monthly_remaining: 0,
    features: {
      can_job_match: true,
      can_auto_apply: false,
      can_run_continuous_auto_apply: false,
      can_use_assistant: true,
      max_auto_apply_per_day: 0,
      monthly_application_limit: 0,
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
  const [jobAlertsEnabled, setJobAlertsEnabled] = useState(false);
  const [workPreferences, setWorkPreferences] = useState("");
  const [companyRankingFilter, setCompanyRankingFilter] = useState("any");
  const [companiesToAvoid, setCompaniesToAvoid] = useState("");
  const [maxApplicationsPerDay, setMaxApplicationsPerDay] = useState("10");
  const [minimumMatchScore, setMinimumMatchScore] = useState("30");
  const [subProfiles, setSubProfiles] = useState<SubProfile[]>([]);
  const [activeSubProfileId, setActiveSubProfileId] = useState("");
  const [subProfileName, setSubProfileName] = useState("");
  const [subProfileKpiFocus, setSubProfileKpiFocus] = useState("");
  const [bookmarks, setBookmarks] = useState<BookmarkEntry[]>([]);
  const [bookmarkCompany, setBookmarkCompany] = useState("");
  const [bookmarkWebsite, setBookmarkWebsite] = useState("");
  const [bookmarkNote, setBookmarkNote] = useState("");
  const [permissionRequests, setPermissionRequests] = useState<PermissionRequest[]>([]);
  const [permissionCaptureJobId, setPermissionCaptureJobId] = useState("");
  const [permissionApplicationUrl, setPermissionApplicationUrl] = useState("");
  const [permissionNote, setPermissionNote] = useState("");
  const [autoApplyQueue, setAutoApplyQueue] = useState<AutoApplyQueueItem[]>([]);

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [results, setResults] = useState<MatchResult[]>([]);
  const [discoveryDiagnostics, setDiscoveryDiagnostics] = useState<DiscoveryDiagnostics | null>(null);
  const [postedWindow, setPostedWindow] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
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
  const [activeStep, setActiveStep] = useState<DashboardStep>("dashboard");
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [appFilter, setAppFilter] = useState<"all" | "in_flight" | "needs_you" | "rejected" | "withdrawn">("all");
  const [submittingAll, setSubmittingAll] = useState(false);

  const [resumeStoragePath, setResumeStoragePath] = useState("");
  const [resumeStorageFilename, setResumeStorageFilename] = useState("");
  const [tailoredDocuments, setTailoredDocuments] = useState<TailoredDocument[]>([]);
  const [tailorJobUrl, setTailorJobUrl] = useState("");
  const [tailorMode, setTailorMode] = useState<"resume" | "cover_letter">("resume");
  const [tailorLoading, setTailorLoading] = useState(false);
  const [tailorResult, setTailorResult] = useState<{ tailored_text: string; changes: string[]; keywords: string[] } | null>(null);

  const selectedCountry = useMemo(
    () => profileOptions.countries.find((entry) => entry.label === country),
    [country, profileOptions.countries]
  );
  const availableRegions = selectedCountry?.regions ?? [];
  const testingPremiumMode = subscription.testing_mode || subscription.status === "testing";
  const autoApplyLocked = !testingPremiumMode && !subscription.features.can_auto_apply;
  const recentApplications = useMemo(() => applications.slice(0, 6), [applications]);
  const recentBookmarks = useMemo(() => bookmarks.slice(0, 8), [bookmarks]);
  const sourceOptions = useMemo(() => {
    const seen = new Set<string>();
    return results
      .map((item) => item.source)
      .filter((item) => {
        if (!item || seen.has(item)) return false;
        seen.add(item);
        return true;
      })
      .sort();
  }, [results]);
  const filteredResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return results.filter((item) => {
      if (q && !`${item.title} ${item.company}`.toLowerCase().includes(q)) return false;
      if (sourceFilter !== "all" && item.source !== sourceFilter) return false;
      if (postedWindow === "24h") return item.posted_bucket === "past_24_hours";
      if (postedWindow === "7d") return item.posted_bucket === "past_24_hours" || item.posted_bucket === "past_week";
      if (postedWindow === "30d") return item.posted_bucket !== "older" && item.posted_bucket !== "unknown";
      if (postedWindow === "older") return item.posted_bucket === "older";
      return true;
    });
  }, [postedWindow, results, sourceFilter, searchQuery]);
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

  const applicationAnswers = useMemo(() => {
    const answers: { question: string; answer: string }[] = [];
    if (country) {
      answers.push({
        question: `Legally authorized to work in ${country}?`,
        answer: workAuthorizationStatus && !needsSponsorship ? "Yes" : workAuthorizationStatus ? "Yes" : "No"
      });
    }
    answers.push({ question: "Require visa sponsorship (now or future)?", answer: needsSponsorship ? "Yes" : "No" });
    if (workAuthorizationStatus) answers.push({ question: "Work authorization status", answer: workAuthorizationStatus });
    answers.push({ question: "Willing to relocate?", answer: willingToRelocate ? "Yes" : "No" });
    if (salaryExpectation) answers.push({ question: "Salary expectation", answer: salaryExpectation });
    return answers;
  }, [country, workAuthorizationStatus, needsSponsorship, willingToRelocate, salaryExpectation]);

  const applicationsByStage = useMemo(() => {
    const map: Record<string, ApplicationRecord[]> = {};
    for (const stage of PIPELINE_STAGES) map[stage.key] = [];
    for (const app of applications) {
      const stage = PIPELINE_STAGES.find((s) => s.statuses.includes(app.status));
      if (stage) map[stage.key].push(app);
    }
    return map;
  }, [applications]);

  const IN_FLIGHT_STATUSES = ["queued_auto_apply", "viewed", "applied", "replied", "interviewing"];
  const needsYouCount = useMemo(
    () => applications.filter((a) => a.status === "approval_required").length,
    [applications]
  );
  const topMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const list = q
      ? matches.filter((m) => `${m.title} ${m.company}`.toLowerCase().includes(q))
      : matches;
    return list;
  }, [matches, searchQuery]);
  const filteredApplications = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return applications.filter((a) => {
      if (q && !`${a.title} ${a.company}`.toLowerCase().includes(q)) return false;
      if (appFilter === "all") return true;
      if (appFilter === "in_flight") return IN_FLIGHT_STATUSES.includes(a.status);
      if (appFilter === "needs_you") return a.status === "approval_required";
      if (appFilter === "rejected") return a.status === "rejected";
      if (appFilter === "withdrawn") return a.status === "withdrawn";
      return true;
    });
  }, [applications, appFilter, searchQuery]);
  function tailoredFor(app: ApplicationRecord, mode: "resume" | "cover_letter"): string {
    const key = `${mode}::${(app.company || "").toLowerCase()}::${(app.title || "").toLowerCase()}`;
    return tailoredDocuments.some((d) => d.id === key) ? "Ready" : mode === "resume" ? "Default" : "Off";
  }
  function ringColor(score: number): string {
    if (score >= 80) return "#16a34a";
    if (score >= 55) return "#ea580c";
    return "#0a0a0a";
  }
  function statusMeta(status: string): { label: string; tone: string } {
    switch (status) {
      case "applied":
        return { label: "Submitted", tone: "green" };
      case "replied":
        return { label: "Replied", tone: "green" };
      case "interviewing":
        return { label: "Interview", tone: "blue" };
      case "viewed":
        return { label: "Viewed", tone: "slate" };
      case "queued_auto_apply":
        return { label: "Queued", tone: "amber" };
      case "approval_required":
        return { label: "Needs you", tone: "red" };
      case "rejected":
        return { label: "Failed", tone: "red" };
      case "withdrawn":
        return { label: "Skipped", tone: "slate" };
      default:
        return { label: status.replace(/_/g, " "), tone: "slate" };
    }
  }
  function relativeTime(iso?: string): string {
    if (!iso) return "—";
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return "—";
    const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
    if (secs < 60) return "just now";
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
    const months = Math.floor(days / 30);
    return `${months} month${months === 1 ? "" : "s"} ago`;
  }

  useEffect(() => {
    let mounted = true;
    async function bootstrap() {
      const { data } = await supabase.auth.getSession();
      const session = data.session;
      if (!session) {
        router.push("/login");
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
        loadAssistantState(session.access_token),
        loadJobMatches(session.access_token)
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
      dashboard: "dashboard-home",
      profile: "profile",
      matched_jobs: "results",
      bookmarks: "bookmarks",
      auto_apply: "automation",
      analytics: "analytics-metrics",
      tracker: "analytics-metrics"
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
      return "Your Anthropic key is invalid in Render. Update ANTHROPIC_API_KEY, redeploy Render, and reopen the assistant.";
    }
    if (normalized.includes("insufficient balance") || normalized.includes("balance is empty")) {
      return "The Anthropic assistant account does not have available billing or credit right now. Check Anthropic billing, redeploy if needed, and try again.";
    }
    if (normalized.includes("model:") || normalized.includes("not found") || normalized.includes("claude-")) {
      return "Your ANTHROPIC_MODEL value in Render is likely malformed or points to a retired model. Set it to a current model such as claude-sonnet-4-5 with no quotes, save, redeploy Render, and try again.";
    }
    if (normalized.includes("quota") || normalized.includes("rate limit")) {
      return "The Anthropic assistant hit a quota, billing limit, or rate-limit issue. Check Anthropic billing and usage for the key configured in Render, then try again.";
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
    const nextSubProfiles = [next, ...subProfiles.filter((item) => item.id !== identifier)].slice(0, 8);
    setSubProfiles(nextSubProfiles);
    setActiveSubProfileId(identifier);
    void persistProfile(
      buildProfilePayload({ sub_profiles: nextSubProfiles, active_sub_profile_id: identifier }),
      { advanceStep: null, silent: false, successMessage: `Saved sub profile: ${next.name}` }
    );
  }

  function removeSubProfile(id: string): void {
    const nextSubProfiles = subProfiles.filter((item) => item.id !== id);
    const nextActive = activeSubProfileId === id ? "" : activeSubProfileId;
    setSubProfiles(nextSubProfiles);
    if (activeSubProfileId === id) {
      setActiveSubProfileId("");
      setSubProfileName("");
      setSubProfileKpiFocus("");
    }
    void persistProfile(
      buildProfilePayload({ sub_profiles: nextSubProfiles, active_sub_profile_id: nextActive }),
      { advanceStep: null, silent: true, successMessage: null }
    );
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
      setJobAlertsEnabled(Boolean(app.job_alerts_enabled));
      setTailoredDocuments(Array.isArray(app.tailored_documents) ? app.tailored_documents : []);
      setResumeStoragePath(app.resume_storage_path ?? "");
      setResumeStorageFilename(app.resume_filename ?? "");
      setWorkPreferences((app.work_preferences || []).join(", "));
      setCompanyRankingFilter(app.company_ranking_filter ?? "any");
      setCompaniesToAvoid(app.companies_to_avoid ?? "");
      setMaxApplicationsPerDay(String(app.max_applications_per_day ?? 10));
      setMinimumMatchScore(String(app.minimum_match_score ?? 30));
      setBookmarks(Array.isArray(app.bookmarks) ? app.bookmarks : []);
      setPermissionRequests(Array.isArray(app.permission_requests) ? app.permission_requests : []);
      setAutoApplyQueue(
        Array.isArray(app.auto_apply_queue)
          ? (app.auto_apply_queue as Array<Record<string, unknown>>).map((item) => ({
              id: String(item?.id ?? ""),
              title: String(item?.title ?? ""),
              company: String(item?.company ?? ""),
              location: String(item?.location ?? ""),
              source: String(item?.source ?? ""),
              url: String(item?.url ?? ""),
              posted_relative: String(item?.posted_relative ?? ""),
              final_score: Number(item?.final_score ?? 0),
              ats_score: Number(item?.ats_score ?? 0),
              permission_required: Boolean(item?.permission_required),
              application_url: String(item?.application_url ?? ""),
            }))
          : []
      );
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

  async function loadJobMatches(accessToken: string = token, roleQuery?: string): Promise<void> {
    if (!isBackendConfigured()) return;
    setMatchesLoading(true);
    try {
      // Prefer an explicit role (e.g. after profile load); otherwise let the
      // backend use the user's SAVED profile target_role (avoids the stale
      // closed-over default targetRole from the initial render).
      const q = (roleQuery ?? "").trim();
      const res = await fetch(
        `${backendUrl}/api/jobs/matches?limit=24${q ? `&q=${encodeURIComponent(q)}` : ""}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      const data = await res.json();
      setMatches(Array.isArray(data?.results) ? data.results : []);
    } catch (err) {
      console.error(err);
    } finally {
      setMatchesLoading(false);
    }
  }

  async function applyToJob(job: MatchResult): Promise<void> {
    // Always open the posting so the action does something even if queuing is gated.
    if (typeof window !== "undefined" && job.url) {
      window.open(normalizeBookmarkWebsite(job.url), "_blank", "noopener,noreferrer");
    }
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    // Create a real application row via auto-apply/run so it shows in the table
    // and Submit all can pick it up. This is consent-gated on the backend.
    try {
      const res = await authFetch(`${backendUrl}/api/auto-apply/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: "custom",
          custom_role: targetRole,
          max_jobs: 1,
          selected_jobs: [buildQueueItem(job)]
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Could not queue this application.");
      await loadApplications();
      await loadSubscription();
      setMessage(
        `${job.title} at ${job.company}: ${data?.message ?? "queued"}. It's now in your applications table.`
      );
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Could not queue this application.";
      setMessage(
        `${detail} Tip: Auto Apply needs a Pro plan plus Auto Apply + consent enabled under Settings.`
      );
    }
  }

  async function submitAllQueued(): Promise<void> {
    const queued = applications.filter(
      (a) => a.status === "queued_auto_apply" || a.status === "approval_required"
    );
    if (!queued.length) {
      setMessage("No queued applications to submit yet. Move matched jobs into the queue first.");
      return;
    }
    setSubmittingAll(true);
    let ok = 0;
    try {
      for (const application of queued) {
        try {
          const res = await authFetch(`${backendUrl}/api/auto-apply/submit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ application_id: application.id, dry_run: false })
          });
          if (res.ok) ok += 1;
        } catch {
          /* continue with the rest */
        }
      }
      await loadApplications();
      setMessage(`Submit all: ran ${ok}/${queued.length} through the engine. Updated statuses below.`);
    } finally {
      setSubmittingAll(false);
    }
  }

  async function updateApplicationStatus(applicationId: number, status: string): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    try {
      const res = await authFetch(`${backendUrl}/api/applications/${applicationId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Could not update application.");
      await loadApplications();
      setMessage(`Application marked as ${status.replace(/_/g, " ")}.`);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Application update failed.";
      setMessage(detail);
    }
  }

  async function uploadResumeToStorage(file: File): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    setMessage("Uploading resume…");
    try {
      const formData = new FormData();
      formData.set("resume_file", file);
      const res = await authFetch(`${backendUrl}/api/resume/upload`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Resume upload failed.");
      setResumeStoragePath(data.resume_storage_path ?? "");
      setResumeStorageFilename(data.resume_filename ?? "");
      setMessage(`Resume saved for auto-submit: ${data.resume_filename ?? ""}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Resume upload failed.");
    }
  }

  async function submitApplication(applicationId: number): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    setMessage("Running the submission engine (headless browser)…");
    try {
      const res = await authFetch(`${backendUrl}/api/auto-apply/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ application_id: applicationId, dry_run: false })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Submission failed.");
      const result = data.result ?? {};
      await loadApplications();
      const suffix = data.dry_run ? " (dry run — approval still required)" : "";
      const err = result.error ? ` — ${result.error}` : "";
      setMessage(`Submission engine: ${result.status ?? "done"}${suffix}${err}`);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Submission failed.";
      setMessage(detail);
    }
  }

  async function tailorForJob(job: MatchResult, mode: "resume" | "cover_letter"): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    setTailorJobUrl(job.url);
    setTailorMode(mode);
    setTailorResult(null);
    setTailorLoading(true);
    try {
      const res = await authFetch(`${backendUrl}/api/tailor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          job_title: job.title,
          company: job.company,
          job_description: "",
          base_text: applicationSummary
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Tailoring failed.");
      if (data?.subscription) setSubscription(data.subscription);
      setTailorResult({
        tailored_text: data.tailored_text ?? "",
        changes: Array.isArray(data.changes) ? data.changes : [],
        keywords: Array.isArray(data.keywords) ? data.keywords : []
      });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Tailoring failed.";
      setMessage(humanizeAssistantError(detail));
      setTailorJobUrl("");
    } finally {
      setTailorLoading(false);
    }
  }

  async function saveTailoredDocument(job: MatchResult): Promise<void> {
    if (!tailorResult) return;
    const doc: TailoredDocument = {
      id: `${tailorMode}::${job.company.toLowerCase()}::${job.title.toLowerCase()}`,
      mode: tailorMode,
      company: job.company,
      job_title: job.title,
      tailored_text: tailorResult.tailored_text,
      changes: tailorResult.changes,
      keywords: tailorResult.keywords,
      created_at: new Date().toISOString()
    };
    const next = [doc, ...tailoredDocuments.filter((d) => d.id !== doc.id)].slice(0, 50);
    setTailoredDocuments(next);
    setTailorJobUrl("");
    setTailorResult(null);
    await persistProfile(buildProfilePayload({ tailored_documents: next }), {
      advanceStep: null,
      silent: false,
      successMessage: "Tailored document saved."
    });
  }

  async function removeTailoredDocument(id: string): Promise<void> {
    const next = tailoredDocuments.filter((d) => d.id !== id);
    setTailoredDocuments(next);
    await persistProfile(buildProfilePayload({ tailored_documents: next }), {
      advanceStep: null,
      silent: false,
      successMessage: "Tailored document removed."
    });
  }

  async function copyText(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      setMessage("Copied to clipboard.");
    } catch {
      setMessage("Could not copy from this browser.");
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

  function buildProfilePayload(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
    const skills = skillsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return {
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
      job_alerts_enabled: jobAlertsEnabled,
      tailored_documents: tailoredDocuments,
      resume_storage_path: resumeStoragePath,
      resume_filename: resumeStorageFilename,
      company_ranking_filter: companyRankingFilter,
      companies_to_avoid: companiesToAvoid,
      max_applications_per_day: Number(maxApplicationsPerDay || "10"),
      minimum_match_score: Number(minimumMatchScore || "30"),
      application_summary: applicationSummary,
      bookmarks,
      permission_requests: permissionRequests,
      auto_apply_queue: autoApplyQueue,
      sub_profiles: subProfiles,
      active_sub_profile_id: activeSubProfileId,
      ...overrides
    };
  }

  async function persistProfile(
    payload: Record<string, unknown>,
    options: PersistProfileOptions = {}
  ): Promise<boolean> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return false;
    }
    const { advanceStep = "matched_jobs", silent = false, successMessage = "Profile saved." } = options;
    try {
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
      if (advanceStep) {
        setActiveStep(advanceStep);
      }
      if (!silent && successMessage) {
        setMessage(successMessage);
      }
      return true;
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Profile update failed.";
      if (detail === "Failed to fetch") {
        setMessage("Failed to fetch backend. Check NEXT_PUBLIC_BACKEND_URL and Render CORS settings.");
      } else {
        setMessage(detail);
      }
      return false;
    }
  }

  async function saveProfile(options: PersistProfileOptions = {}): Promise<boolean> {
    return persistProfile(buildProfilePayload(), options);
  }

  function createBookmarkId(companyValue: string, websiteValue: string): string {
    const cleanCompany = companyValue.trim().toLowerCase();
    const cleanWebsite = websiteValue.trim().toLowerCase();
    if (cleanCompany || cleanWebsite) {
      return `${cleanCompany}::${cleanWebsite}`;
    }
    return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`;
  }

  function normalizeBookmarkWebsite(raw: string): string {
    const trimmed = raw.trim();
    if (!trimmed) return "";
    if (/^https?:\/\//i.test(trimmed)) return trimmed;
    return `https://${trimmed}`;
  }

  async function persistBookmarks(nextBookmarks: BookmarkEntry[], successMessage: string): Promise<void> {
    setBookmarks(nextBookmarks);
    await persistProfile(buildProfilePayload({ bookmarks: nextBookmarks }), {
      advanceStep: null,
      successMessage,
      silent: false
    });
  }

  async function addManualBookmark(): Promise<void> {
    const companyValue = bookmarkCompany.trim();
    const websiteValue = normalizeBookmarkWebsite(bookmarkWebsite);
    if (!companyValue || !websiteValue) {
      setMessage("Add both a company name and website before saving a bookmark.");
      return;
    }
    const nextBookmarks = [
      {
        id: createBookmarkId(companyValue, websiteValue),
        company: companyValue,
        website: websiteValue,
        note: bookmarkNote.trim(),
        created_at: new Date().toISOString()
      },
      ...bookmarks.filter((item) => item.company.toLowerCase() !== companyValue.toLowerCase() || item.website.toLowerCase() !== websiteValue.toLowerCase())
    ];
    setBookmarkCompany("");
    setBookmarkWebsite("");
    setBookmarkNote("");
    await persistBookmarks(nextBookmarks, `${companyValue} saved to bookmarks.`);
  }

  async function bookmarkJob(job: MatchResult): Promise<void> {
    const websiteValue = normalizeBookmarkWebsite(job.url);
    const nextBookmarks = [
      {
        id: createBookmarkId(job.company, websiteValue),
        company: job.company,
        website: websiteValue,
        note: `${job.title} | ${job.source}${job.posted_relative ? ` | Posted ${job.posted_relative}` : ""}`,
        created_at: new Date().toISOString()
      },
      ...bookmarks.filter((item) => item.company.toLowerCase() !== job.company.toLowerCase() || item.website.toLowerCase() !== websiteValue.toLowerCase())
    ];
    await persistBookmarks(nextBookmarks, `${job.company} saved to bookmarks.`);
  }

  async function removeBookmark(bookmarkId: string): Promise<void> {
    const nextBookmarks = bookmarks.filter((item) => item.id !== bookmarkId);
    await persistBookmarks(nextBookmarks, "Bookmark removed.");
  }

  async function copyBookmarkWebsite(website: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(website);
      setMessage("Bookmark website copied.");
    } catch {
      setMessage("Could not copy the bookmark website from this browser.");
    }
  }


  function buildQueueItem(job: MatchResult, overrides: Partial<AutoApplyQueueItem> = {}): AutoApplyQueueItem {
    return {
      id: `${job.company.toLowerCase()}::${job.title.toLowerCase()}::${job.url.toLowerCase()}`,
      title: job.title,
      company: job.company,
      location: job.location,
      source: job.source,
      url: job.url,
      posted_relative: job.posted_relative,
      final_score: job.final_score,
      ats_score: job.ats_score,
      permission_required: false,
      application_url: "",
      ...overrides,
    };
  }

  function getPermissionRequestForJob(job: MatchResult): PermissionRequest | undefined {
    return permissionRequests.find(
      (item) =>
        item.source_url === job.url ||
        (item.company.toLowerCase() === job.company.toLowerCase() &&
          item.title.toLowerCase() === job.title.toLowerCase())
    );
  }

  function openPermissionRequired(job: MatchResult): void {
    const existing = getPermissionRequestForJob(job);
    const targetUrl = normalizeBookmarkWebsite(existing?.application_url || job.url);
    setPermissionCaptureJobId(job.url);
    setPermissionApplicationUrl(existing?.application_url || job.url);
    setPermissionNote(existing?.note || "");
    if (targetUrl && typeof window !== "undefined") {
      window.open(targetUrl, "_blank", "noopener,noreferrer");
      setMessage("Opened the application page in a new tab. Save the direct application URL here if you want it queued for Auto Apply.");
      return;
    }
    setMessage("Add a direct application URL for this permission-required job.");
  }

  async function addJobToAutoApplyQueue(
    job: MatchResult,
    overrides: Partial<AutoApplyQueueItem> = {},
    nextPermissionRequests: PermissionRequest[] = permissionRequests,
    navigate: boolean = true
  ): Promise<void> {
    const nextItem = buildQueueItem(job, overrides);
    const nextQueue = [nextItem, ...autoApplyQueue.filter((item) => item.id !== nextItem.id)];
    setAutoApplyQueue(nextQueue);
    if (navigate) {
      setActiveStep("auto_apply");
      setMessage(`${job.title} moved into the Auto Apply queue.`);
    }
    await persistProfile(
      buildProfilePayload({
        permission_requests: nextPermissionRequests,
        auto_apply_queue: nextQueue,
      }),
      {
        advanceStep: null,
        silent: true,
        successMessage: null,
      }
    );
  }

  async function savePermissionRequest(job: MatchResult): Promise<void> {
    const applicationUrl = normalizeBookmarkWebsite(permissionApplicationUrl || job.url);
    if (!applicationUrl) {
      setMessage("Add an application URL before saving a permission-required job.");
      return;
    }
    const requestId = `${job.company.toLowerCase()}::${job.title.toLowerCase()}::${applicationUrl.toLowerCase()}`;
    const nextPermissionRequests: PermissionRequest[] = [
      {
        id: requestId,
        company: job.company,
        title: job.title,
        source_url: job.url,
        application_url: applicationUrl,
        note: permissionNote.trim(),
        created_at: new Date().toISOString(),
      },
      ...permissionRequests.filter((item) => item.id !== requestId),
    ];
    setPermissionRequests(nextPermissionRequests);
    setPermissionCaptureJobId("");
    setPermissionApplicationUrl("");
    setPermissionNote("");
    await addJobToAutoApplyQueue(
      job,
      {
        permission_required: true,
        application_url: applicationUrl,
      },
      nextPermissionRequests
    );
  }

  async function removeQueuedJob(jobId: string): Promise<void> {
    const nextQueue = autoApplyQueue.filter((item) => item.id !== jobId);
    setAutoApplyQueue(nextQueue);
    await persistProfile(
      buildProfilePayload({
        auto_apply_queue: nextQueue,
      }),
      {
        advanceStep: null,
        silent: true,
        successMessage: null,
      }
    );
  }

  async function runMatch(): Promise<void> {
    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    if (!resumeFile) {
      setMessage("Upload a resume before running job matching.");
      return;
    }
    const saved = await saveProfile({ advanceStep: null, silent: true, successMessage: null });
    if (!saved) return;
    setMessage("Matching jobs...");
    setResults([]);
    setDiscoveryDiagnostics(null);
    try {
      const formData = new FormData();
      formData.set("resume_file", resumeFile);
      formData.set("role", "custom");
      formData.set("custom_role", targetRole);
      formData.set("top_k", "50");
      formData.set("min_score", "1.2");

      const res = await authFetch(`${backendUrl}/api/rag/match`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Match request failed.");
      setResults(data.results ?? []);
      setDiscoveryDiagnostics(data.source_diagnostics ?? null);
      setPostedWindow("all");
      setSourceFilter("all");
      setActiveStep("matched_jobs");
      setMessage(
        data?.message ??
          `Found ${data.count ?? 0} matching jobs from ${data.scanned_jobs ?? 0} scanned openings.`
      );
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Failed to match jobs.";
      if (detail === "Failed to fetch") {
        setMessage("Failed to fetch backend. Check NEXT_PUBLIC_BACKEND_URL and Render CORS settings.");
        return;
      }
      setMessage(detail);
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
    const saved = await saveProfile({ advanceStep: null, silent: true, successMessage: null });
    if (!saved) return;
    const selectedJobs = autoApplyQueue.length
      ? autoApplyQueue
      : filteredResults.slice(0, 12).map((job) => buildQueueItem(job));
    if (!selectedJobs.length) {
      setMessage("Move matched jobs into Auto Apply first, or run matching to build a queue.");
      return;
    }
    try {
      const res = await authFetch(`${backendUrl}/api/auto-apply/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: "custom",
          custom_role: targetRole,
          max_jobs: 12,
          selected_jobs: selectedJobs,
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Auto Apply failed.");
      await loadApplications();
      await loadSubscription();
      setAutoApplyQueue([]);
      setShowApplications(true);
      setActiveStep("analytics");
      setMessage(
        data?.message ??
          `Auto Apply completed. Matched ${data.matched_jobs}, queued ${data.queued_applications}.`
      );
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Auto Apply failed.";
      if (detail === "Failed to fetch") {
        setMessage("Auto Apply could not reach the backend. Redeploy Render with the latest code, then try again.");
        return;
      }
      setMessage(detail);
    }
  }

  async function startCheckout(): Promise<void> {

    if (!isBackendConfigured()) {
      setMessage(backendConfigMessage());
      return;
    }
    if (subscription.plan !== "basic" && subscription.status !== "inactive") {
      setMessage("This account already has a paid plan.");
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
      <aside className="dashboard-sidebar tsenta-sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-logo-mark">A</span>
          <span className="sidebar-logo-word">AIapply.ai</span>
        </div>

        <p className="sidebar-section-label">Dashboard</p>
        <nav className="sidebar-nav" aria-label="Dashboard sections">
          <button type="button" className={`sidebar-link${activeStep === "dashboard" ? " active" : ""}`} onClick={() => setActiveStep("dashboard")}>
            <span className="nav-ico">▦</span><span className="nav-text">Dashboard</span>
          </button>
          <button type="button" className={`sidebar-link${activeStep === "matched_jobs" ? " active" : ""}`} onClick={() => setActiveStep("matched_jobs")}>
            <span className="nav-ico">⌕</span><span className="nav-text">Browse jobs</span>
          </button>
          <button type="button" className={`sidebar-link${activeStep === "analytics" ? " active" : ""}`} onClick={() => setActiveStep("analytics")}>
            <span className="nav-ico">▤</span><span className="nav-text">Applications</span>
            {applicationsCount > 0 && <span className="nav-badge">{applicationsCount}</span>}
          </button>
          <button
            type="button"
            className="sidebar-link"
            onClick={() => {
              setAppFilter("needs_you");
              setActiveStep("dashboard");
            }}
          >
            <span className="nav-ico">✉</span><span className="nav-text">Inbox</span>
            {needsYouCount > 0 && <span className="nav-badge">{needsYouCount}</span>}
          </button>
          <button type="button" className={`sidebar-link${activeStep === "tracker" ? " active" : ""}`} onClick={() => setActiveStep("tracker")}>
            <span className="nav-ico">▤</span><span className="nav-text">Tracker</span>
          </button>
        </nav>

        <div className="sidebar-divider" />
        <nav className="sidebar-nav" aria-label="Account">
          <button type="button" className={`sidebar-link${activeStep === "profile" ? " active" : ""}`} onClick={() => setActiveStep("profile")}>
            <span className="nav-ico">◔</span><span className="nav-text">Profile</span>
          </button>
          <button type="button" className={`sidebar-link${activeStep === "auto_apply" ? " active" : ""}`} onClick={() => setActiveStep("auto_apply")}>
            <span className="nav-ico">⚙</span><span className="nav-text">Settings</span>
          </button>
        </nav>

        <div className="sidebar-foot">
          <button type="button" className="help-box" onClick={() => setAssistantOpen(true)}>
            <span className="help-ico">?</span>
            <span>
              <strong>Help &amp; support</strong>
              <span className="help-sub">Ask the assistant</span>
            </span>
          </button>
          <button type="button" className="user-card" onClick={signOut} title="Click to sign out">
            <span className="user-avatar">{(fullName || userEmail || "U").slice(0, 2).toUpperCase()}</span>
            <span className="user-meta">
              <strong>{fullName || userEmail || "Your account"}</strong>
              <span className="user-sub">{subscription.label} plan</span>
            </span>
          </button>
        </div>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-topbar tsenta-topbar">
          <h2 className="topbar-title">
            {activeStep === "dashboard"
              ? "Dashboard"
              : activeStep === "matched_jobs"
                ? "Browse jobs"
                : activeStep === "analytics"
                  ? "Applications"
                  : activeStep === "tracker"
                    ? "Tracker"
                    : activeStep === "profile"
                      ? "Profile"
                      : activeStep === "auto_apply"
                        ? "Settings"
                        : "Bookmarks"}
          </h2>
          {(activeStep === "dashboard" || activeStep === "matched_jobs") ? (
            <input
              className="topbar-search"
              type="search"
              placeholder="Search by title, company..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          ) : (
            <span className="topbar-search-spacer" />
          )}
          <div className="topbar-icons">
            <button
              type="button"
              className="icon-btn"
              title={`${needsYouCount} applications need you`}
              aria-label="Notifications"
              onClick={() => {
                setAppFilter("needs_you");
                setActiveStep("dashboard");
              }}
            >
              🔔{needsYouCount > 0 && <span className="icon-dot" />}
            </button>
            <button
              type="button"
              className="icon-btn"
              title="Help / assistant"
              aria-label="Help"
              onClick={() => setAssistantOpen(true)}
            >
              ?
            </button>
          </div>
        </header>

        {message && <div className="status-banner">{message}</div>}

        {/* ---- Dashboard home (Tsenta-style) ---- */}
        <section
          id="dashboard-home"
          className="tsenta-home"
          style={activeStep === "dashboard" ? undefined : { display: "none" }}
        >
          <div className="card-header-row">
            <h3>Top job matches</h3>
            <button type="button" className="ghost" onClick={() => setActiveStep("matched_jobs")}>
              Browse Jobs ›
            </button>
          </div>
          <div className="match-grid">
            {matchesLoading && topMatches.length === 0 ? (
              <p className="empty-state">Finding matches…</p>
            ) : topMatches.length === 0 ? (
              <p className="empty-state">
                No matches yet. Set your target role in Profile, then check back — or use Browse jobs.
              </p>
            ) : (
              topMatches.slice(0, 4).map((job, i) => (
                <article key={job.url || i} className={`match-card tint-${i % 4}`}>
                  <div className="match-card-top">
                    <div>
                      <p className="match-company">{job.company}</p>
                      <h4>{job.title}</h4>
                    </div>
                    <span
                      className="match-ring"
                      style={{
                        background: `conic-gradient(${ringColor(job.ats_score)} ${job.ats_score * 3.6}deg, rgba(0,0,0,0.08) 0deg)`
                      }}
                    >
                      <span className="match-ring-label">{job.ats_score}%</span>
                    </span>
                  </div>
                  <div className="match-card-foot">
                    <span className="match-source">{job.source}</span>
                    <button type="button" onClick={() => void applyToJob(job)}>Apply</button>
                  </div>
                </article>
              ))
            )}
          </div>

          <div className="card-header-row applications-head">
            <h3>All applications</h3>
            <div className="inline-actions">
              <button type="button" className="ghost" onClick={() => setActiveStep("tracker")}>Open Tracker</button>
              <button type="button" onClick={() => void submitAllQueued()} disabled={submittingAll}>
                {submittingAll ? "Submitting…" : "Submit all"}
              </button>
            </div>
          </div>
          <div className="app-filter-tabs">
            {([
              ["all", "All"],
              ["in_flight", "In flight"],
              ["needs_you", "Needs you"],
              ["rejected", "Failed"],
              ["withdrawn", "Skipped"]
            ] as const).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`app-tab${appFilter === key ? " active" : ""}`}
                onClick={() => setAppFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="app-table-wrap">
            <table className="app-table">
              <thead>
                <tr>
                  <th>Position</th>
                  <th>Resume</th>
                  <th>Cover Letter</th>
                  <th>Status</th>
                  <th>Applied</th>
                </tr>
              </thead>
              <tbody>
                {filteredApplications.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="empty-state">No applications in this view yet.</td>
                  </tr>
                ) : (
                  filteredApplications.map((app) => {
                    const meta = statusMeta(app.status);
                    return (
                      <tr
                        key={app.id}
                        className="app-row"
                        onClick={() =>
                          app.job_url && window.open(normalizeBookmarkWebsite(app.job_url), "_blank", "noopener,noreferrer")
                        }
                      >
                        <td>
                          <div className="app-position">
                            <span className="app-avatar">{(app.company || "?").slice(0, 1).toUpperCase()}</span>
                            <span>
                              <strong>{app.company || "Unknown company"}</strong>
                              <span className="app-role">{app.title || "Untitled role"}</span>
                            </span>
                          </div>
                        </td>
                        <td className="app-doc">{tailoredFor(app, "resume")}</td>
                        <td className="app-doc">{tailoredFor(app, "cover_letter")}</td>
                        <td>
                          <span className={`status-dot-label tone-${meta.tone}`}>
                            <span className="status-dot" />
                            {meta.label}
                          </span>
                        </td>
                        <td className="app-applied">{relativeTime(app.created_at)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section
          className="metric-grid"
          id="analytics-metrics"
          style={activeStep === "dashboard" ? { display: "none" } : undefined}
        >
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
            <p className="metric-label">Bookmarks</p>
            <strong>{bookmarks.length}</strong>
            <span>Saved company targets for later review</span>
          </article>
        </section>

        <section className="dashboard-grid" style={activeStep === "dashboard" ? { display: "none" } : undefined}>
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
                <button onClick={() => void saveProfile()}>Save Profile</button>
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
              <button onClick={runAutoApply} disabled={autoApplyLocked || !autoApplyEnabled || !autoApplyConsent}>
                Run Auto Apply
              </button>
            </div>
            <p className="field-hint">
              Live discovery uses Greenhouse and Lever directly, and also supports LinkedIn, Indeed,
              and other portal imports from the backend `data/imports` folder.
            </p>
            <div className="queue-stat-row">
              <span className="topbar-chip">{autoApplyQueue.length} queued jobs</span>
              <span className="topbar-chip">{permissionRequests.length} permission-required links</span>
              <span className="topbar-chip">{requireApprovalBeforeApply ? "Approval mode" : "Hands-free queue mode"}</span>
            </div>
            <div className="queue-preview-list">
              {autoApplyQueue.length === 0 ? (
                <p className="empty-state">No jobs in the Auto Apply queue yet. Use Move To Auto Apply or Permission Required from matched jobs.</p>
              ) : (
                autoApplyQueue.slice(0, 10).map((job) => (
                  <article key={job.id} className="queue-preview-card">
                    <div className="application-topline">
                      <h4>{job.title}</h4>
                      <span className={`status-pill ${job.permission_required ? "approval_required" : "queued_auto_apply"}`}>
                        {job.permission_required ? "permission required" : "queued"}
                      </span>
                    </div>
                    <p>{job.company} | {job.location} | {job.source}</p>
                    {job.application_url && <p className="bookmark-url">Application URL: {job.application_url}</p>}
                    <div className="feature-actions">
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => {
                          const targetUrl = normalizeBookmarkWebsite(job.application_url || job.url);
                          if (targetUrl && typeof window !== "undefined") {
                            window.open(targetUrl, "_blank", "noopener,noreferrer");
                          }
                        }}
                      >
                        Open Application Page
                      </button>
                      <button type="button" className="ghost" onClick={() => void removeQueuedJob(job.id)}>
                        Remove
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
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
              <label className="dashboard-field-wide">
                Resume for Auto-Submit
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void uploadResumeToStorage(file);
                  }}
                />
                <span className="field-hint">
                  {resumeStorageFilename
                    ? `Stored: ${resumeStorageFilename} (used when the submit engine uploads documents)`
                    : "Upload once; the auto-submit engine attaches this to application forms."}
                </span>
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
                  disabled={!autoApplyEnabled}
                  onChange={(e) => setAutoApplyConsent(e.target.checked)}
                />
              </label>
              <label className="toggle-card">
                <span>Require Approval Before Apply</span>
                <input
                  type="checkbox"
                  checked={requireApprovalBeforeApply}
                  disabled={!autoApplyEnabled}
                  onChange={(e) => setRequireApprovalBeforeApply(e.target.checked)}
                />
              </label>
              <label className="toggle-card">
                <span>Email Me New Matches (Job Alerts)</span>
                <input
                  type="checkbox"
                  checked={jobAlertsEnabled}
                  onChange={(e) => setJobAlertsEnabled(e.target.checked)}
                />
              </label>
            </div>
            {applicationAnswers.length > 0 && (
              <div className="source-diagnostics">
                <p className="feature-kicker">Auto-Answers (work authorization &amp; screening)</p>
                <ul className="plain-list">
                  {applicationAnswers.map((a, i) => (
                    <li key={i}>
                      <strong>{a.question}</strong> {a.answer}
                    </li>
                  ))}
                </ul>
                <p className="field-hint">
                  These pre-fill common ATS screening questions during Auto Apply.
                </p>
              </div>
            )}
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
            <div className="filter-toolbar">
              <label className="compact-filter">
                Posted Window
                <select value={postedWindow} onChange={(e) => setPostedWindow(e.target.value)}>
                  <option value="all">All postings</option>
                  <option value="24h">Past 24 hours</option>
                  <option value="7d">Past week</option>
                  <option value="30d">Past month</option>
                  <option value="older">Older than a month</option>
                </select>
              </label>
              <label className="compact-filter">
                Source
                <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
                  <option value="all">All sources</option>
                  {sourceOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="queue-stat-row">
              <span className="topbar-chip">{filteredResults.length} visible</span>
              <span className="topbar-chip">{results.length} matched</span>
              <span className="topbar-chip">{discoveryDiagnostics?.scanned_jobs ?? 0} scanned</span>
              <span className="topbar-chip">{discoveryDiagnostics?.imports_loaded ?? 0} portal imports</span>
            </div>
            {discoveryDiagnostics && (
              <div className="source-diagnostics">
                <p className="field-hint">
                  {discoveryDiagnostics.imports_loaded > 0
                    ? `Imported ${discoveryDiagnostics.imports_loaded} LinkedIn / Indeed / portal rows from data/imports before live ATS search.`
                    : "LinkedIn, Indeed, and other portal imports are currently empty, so these matches are coming from live Greenhouse and Lever sources."}
                </p>
                {discoveryDiagnostics.source_counts.length > 0 && (
                  <ul className="plain-list">
                    {discoveryDiagnostics.source_counts.slice(0, 12).map((entry) => (
                      <li key={`${entry.source}-${entry.token}`}>
                        <strong>{entry.source}</strong> {entry.token}: {entry.jobs} jobs
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <div className="results-stack">
              {filteredResults.length === 0 ? (
                <p className="empty-state">
                  {results.length === 0
                    ? "No matched jobs yet. Save your targeting profile, upload your resume, and run matching."
                    : "No matched jobs fit the current source or posted-time filters yet."}
                </p>
              ) : (
                filteredResults.map((job) => (
                  <article key={job.url} className="job-row-card">
                    <div>
                      <h4>{job.title}</h4>
                      <p>
                        {job.company} | {job.location} | {job.source}
                        {job.posted_relative ? ` | Posted ${job.posted_relative}` : ""}
                      </p>
                      <p className="field-hint">{job.explanation}</p>
                    </div>
                    <div className="job-row-meta">
                      <span className="topbar-chip">ATS {job.ats_score}%</span>
                      <span className="topbar-chip">Final {job.final_score}/5</span>
                      <span className="status-inline">RAG {job.rag_score}/5</span>
                      <button type="button" className="ghost" onClick={() => void bookmarkJob(job)}>
                        Bookmark
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => openPermissionRequired(job)}
                      >
                        Permission Required
                      </button>
                      <button type="button" className="ghost" onClick={() => void addJobToAutoApplyQueue(job)}>
                        Move To Auto Apply
                      </button>
                      <button type="button" className="ghost" onClick={() => void tailorForJob(job, "resume")}>
                        Tailor Resume
                      </button>
                      <button type="button" className="ghost" onClick={() => void tailorForJob(job, "cover_letter")}>
                        Cover Letter
                      </button>
                    </div>
                    {tailorJobUrl === job.url && (
                      <div className="permission-panel">
                        {tailorLoading ? (
                          <p className="field-hint">Tailoring your {tailorMode === "resume" ? "resume" : "cover letter"} for {job.company}…</p>
                        ) : tailorResult ? (
                          <>
                            <p className="feature-kicker">
                              Tailored {tailorMode === "resume" ? "Resume" : "Cover Letter"} · {job.title} @ {job.company}
                            </p>
                            {tailorResult.keywords.length > 0 && (
                              <p className="field-hint">Aligned keywords: {tailorResult.keywords.join(", ")}</p>
                            )}
                            {tailorResult.changes.length > 0 && (
                              <ul className="plain-list">
                                {tailorResult.changes.slice(0, 12).map((c, i) => (
                                  <li key={i}>{c}</li>
                                ))}
                              </ul>
                            )}
                            <textarea rows={10} readOnly value={tailorResult.tailored_text} />
                            <div className="feature-actions">
                              <button type="button" onClick={() => void saveTailoredDocument(job)}>Save Version</button>
                              <button type="button" className="ghost" onClick={() => void copyText(tailorResult.tailored_text)}>Copy</button>
                              <button
                                type="button"
                                className="ghost"
                                onClick={() => {
                                  setTailorJobUrl("");
                                  setTailorResult(null);
                                }}
                              >
                                Close
                              </button>
                            </div>
                          </>
                        ) : null}
                      </div>
                    )}
                    {permissionCaptureJobId === job.url && (
                      <div className="permission-panel">
                        <label className="dashboard-field-wide">
                          Application URL
                          <input
                            value={permissionApplicationUrl}
                            onChange={(e) => setPermissionApplicationUrl(e.target.value)}
                            placeholder="Paste the direct application page URL"
                          />
                        </label>
                        <label className="dashboard-field-wide">
                          Note (optional)
                          <input
                            value={permissionNote}
                            onChange={(e) => setPermissionNote(e.target.value)}
                            placeholder="Any note about access or recruiter permission"
                          />
                        </label>
                        <div className="feature-actions">
                          <button
                            type="button"
                            className="ghost"
                            onClick={() => {
                              const targetUrl = normalizeBookmarkWebsite(permissionApplicationUrl || job.url);
                              if (targetUrl && typeof window !== "undefined") {
                                window.open(targetUrl, "_blank", "noopener,noreferrer");
                              }
                            }}
                          >
                            Open Application Page
                          </button>
                          <button type="button" onClick={() => void savePermissionRequest(job)}>
                            Save Permission URL
                          </button>
                          <button
                            type="button"
                            className="ghost"
                            onClick={() => {
                              setPermissionCaptureJobId("");
                              setPermissionApplicationUrl("");
                              setPermissionNote("");
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </article>
                ))
              )}
            </div>
          </article>

          <article
            className="dashboard-card dashboard-card-wide"
            id="bookmarks"
            style={activeStep === "bookmarks" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Bookmarks</p>
                <h3>Saved Company Targets</h3>
              </div>
              <span className="status-inline">{bookmarks.length} saved companies</span>
            </div>
            <div className="dashboard-form-grid">
              <label>
                Company Name
                <input value={bookmarkCompany} onChange={(e) => setBookmarkCompany(e.target.value)} placeholder="Anthropic, Vercel, Stripe" />
              </label>
              <label>
                Company Website
                <input value={bookmarkWebsite} onChange={(e) => setBookmarkWebsite(e.target.value)} placeholder="company.com/careers" />
              </label>
              <label>
                Note (optional)
                <input value={bookmarkNote} onChange={(e) => setBookmarkNote(e.target.value)} placeholder="Target for backend, AI, or platform roles" />
              </label>
            </div>
            <div className="inline-actions">
              <button type="button" onClick={() => void addManualBookmark()}>Save Bookmark</button>
            </div>
            <div className="queue-preview-list bookmark-list">
              {recentBookmarks.length === 0 ? (
                <p className="empty-state">No bookmarked companies yet. Save companies here or bookmark them from matched jobs.</p>
              ) : (
                recentBookmarks.map((bookmark) => (
                  <article key={bookmark.id} className="queue-preview-card bookmark-card">
                    <div className="application-topline">
                      <h4>{bookmark.company}</h4>
                      <span className="status-inline">Saved {new Date(bookmark.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="bookmark-url">{bookmark.website}</p>
                    {bookmark.note && <p className="field-hint">{bookmark.note}</p>}
                    <div className="feature-actions">
                      <button type="button" className="ghost" onClick={() => void copyBookmarkWebsite(bookmark.website)}>
                        Copy Website
                      </button>
                      <button type="button" className="ghost" onClick={() => void removeBookmark(bookmark.id)}>
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
                    <div className="feature-actions">
                      {application.status === "approval_required" && (
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => void updateApplicationStatus(application.id, "queued_auto_apply")}
                        >
                          Approve
                        </button>
                      )}
                      {autoApplyEnabled && (application.status === "queued_auto_apply" || application.status === "approval_required") && (
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => void submitApplication(application.id)}
                        >
                          Auto-Submit
                        </button>
                      )}
                      {application.status !== "applied" && application.status !== "withdrawn" && (
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => void updateApplicationStatus(application.id, "applied")}
                        >
                          Mark Applied
                        </button>
                      )}
                      {application.job_url && (
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => {
                            if (typeof window !== "undefined") {
                              window.open(normalizeBookmarkWebsite(application.job_url), "_blank", "noopener,noreferrer");
                            }
                          }}
                        >
                          Open
                        </button>
                      )}
                      {application.status !== "withdrawn" && (
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => void updateApplicationStatus(application.id, "withdrawn")}
                        >
                          Withdraw
                        </button>
                      )}
                    </div>
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
            className="dashboard-card dashboard-card-wide"
            style={activeStep === "analytics" || activeStep === "tracker" ? undefined : { display: "none" }}
          >
            <div className="card-header-row">
              <div>
                <p className="feature-kicker">Pipeline</p>
                <h3>Application Board</h3>
              </div>
              <button onClick={() => void loadApplications()} className="ghost" type="button">
                Refresh
              </button>
            </div>
            <div className="pipeline-board">
              {PIPELINE_STAGES.map((stage) => (
                <div key={stage.key} className="pipeline-column">
                  <div className="pipeline-column-head">
                    <span>{stage.label}</span>
                    <span className="topbar-chip">{applicationsByStage[stage.key]?.length ?? 0}</span>
                  </div>
                  {(applicationsByStage[stage.key] ?? []).length === 0 ? (
                    <p className="empty-state">—</p>
                  ) : (
                    (applicationsByStage[stage.key] ?? []).map((application) => (
                      <article key={application.id} className="pipeline-card">
                        <h4>{application.title || "Untitled role"}</h4>
                        <p>{application.company || "Unknown company"}</p>
                        <div className="feature-actions">
                          {stage.key === "queued" && (
                            <button
                              type="button"
                              className="ghost"
                              onClick={() => void updateApplicationStatus(application.id, "applied")}
                            >
                              Applied
                            </button>
                          )}
                          {stage.key === "applied" && (
                            <button
                              type="button"
                              className="ghost"
                              onClick={() => void updateApplicationStatus(application.id, "replied")}
                            >
                              Replied
                            </button>
                          )}
                          {stage.key === "replied" && (
                            <button
                              type="button"
                              className="ghost"
                              onClick={() => void updateApplicationStatus(application.id, "interviewing")}
                            >
                              Interview
                            </button>
                          )}
                          {application.job_url && (
                            <button
                              type="button"
                              className="ghost"
                              onClick={() => {
                                if (typeof window !== "undefined") {
                                  window.open(normalizeBookmarkWebsite(application.job_url), "_blank", "noopener,noreferrer");
                                }
                              }}
                            >
                              Open
                            </button>
                          )}
                        </div>
                      </article>
                    ))
                  )}
                </div>
              ))}
            </div>
          </article>

          {tailoredDocuments.length > 0 && (
            <article
              className="dashboard-card dashboard-card-wide"
              style={activeStep === "analytics" ? undefined : { display: "none" }}
            >
              <div className="card-header-row">
                <div>
                  <p className="feature-kicker">Saved Documents</p>
                  <h3>Tailored Resumes &amp; Cover Letters</h3>
                </div>
                <span className="status-inline">{tailoredDocuments.length} saved</span>
              </div>
              <div className="queue-preview-list">
                {tailoredDocuments.slice(0, 12).map((doc) => (
                  <article key={doc.id} className="queue-preview-card">
                    <div className="application-topline">
                      <h4>{doc.job_title} @ {doc.company}</h4>
                      <span className="status-pill queued_auto_apply">{doc.mode === "resume" ? "resume" : "cover letter"}</span>
                    </div>
                    {doc.keywords?.length > 0 && <p className="field-hint">Keywords: {doc.keywords.join(", ")}</p>}
                    <div className="feature-actions">
                      <button type="button" className="ghost" onClick={() => void copyText(doc.tailored_text)}>Copy</button>
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => void removeTailoredDocument(doc.id)}
                      >
                        Remove
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </article>
          )}

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
