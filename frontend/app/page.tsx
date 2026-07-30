"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Stage = "find" | "prep" | "apply" | "track";

const STAGES: { key: Stage; label: string; kicker: string; title: string; body: string; points: string[] }[] = [
  {
    key: "find",
    label: "Find",
    kicker: "01 · Discovery",
    title: "The role finds you.",
    body: "AIapply.ai scans public ATS boards continuously and scores every new opening against your resume and preferences, so you see the best matches within minutes of them going live.",
    points: [
      "Greenhouse, Lever, and Ashby sources out of the box",
      "Match score with the overlapping terms that earned it",
      "Live feed + optional email alerts for fresh matches"
    ]
  },
  {
    key: "prep",
    label: "Prep",
    kicker: "02 · Tailoring",
    title: "Tailored materials, reviewed before they go out.",
    body: "For each role, the assistant keyword-aligns your resume and drafts a cover letter grounded only in your real background — and shows you exactly what changed before anything is used.",
    points: [
      "Keyword-aligned to the job, without inventing experience",
      "A change list and matched keywords for every rewrite",
      "Saved tailored versions per company"
    ]
  },
  {
    key: "apply",
    label: "Apply",
    kicker: "03 · Auto-apply",
    title: "Consent-first, never silent.",
    body: "Auto-apply queues roles with explicit consent, daily and monthly caps, and per-application approval. Work-authorization and screening answers are pre-filled from your profile.",
    points: [
      "Explicit consent + approval gates, dry-run by default",
      "OPT / STEM-OPT / H-1B / citizen answers auto-filled",
      "Sponsorship-aware filtering removes roles that won't sponsor"
    ]
  },
  {
    key: "track",
    label: "Track",
    kicker: "04 · Pipeline",
    title: "A pipeline you can actually read.",
    body: "Every application moves through a clear board — queued, viewed, applied, replied, interview — so your search stops living in a spreadsheet.",
    points: [
      "Board view across all pipeline stages",
      "One-click status updates and receipts",
      "Monthly application usage against your plan"
    ]
  }
];

const SURFACES = [
  {
    tag: "01 — web",
    title: "Use it on the web.",
    body: "Match feed, tailoring, application queue, and pipeline board — the whole product in one dashboard, on any browser."
  },
  {
    tag: "02 — chrome",
    title: "Apply from Chrome.",
    body: "On any job posting, the AIapply.ai extension detects the role and lets you match or tailor in one click."
  },
  {
    tag: "03 — mcp / cli",
    title: "Drive it with an agent.",
    body: "An MCP server exposes search, match, and tailor as tools, so Claude Code or any agent that speaks MCP can run your search."
  }
];

const PLANS = [
  {
    name: "Free",
    price: "$0",
    blurb: "Matching and the assistant, to try it out.",
    apps: "Matching only",
    cta: "Get started",
    featured: false
  },
  {
    name: "Starter",
    price: "$19",
    blurb: "Enough for a real job search.",
    apps: "600",
    cta: "Start with Starter",
    featured: false
  },
  {
    name: "Pro",
    price: "$39",
    blurb: "For an active, high-volume search.",
    apps: "1,500",
    cta: "Start Pro",
    featured: true
  },
  {
    name: "Power",
    price: "$99",
    blurb: "Hit every match before anyone else.",
    apps: "4,500",
    cta: "Go Power",
    featured: false
  }
];

const FAQS = [
  {
    q: "How does AIapply.ai find jobs?",
    a: "It scans public applicant-tracking boards (Greenhouse, Lever, and Ashby today) and scores each new role against your resume and preferences. Matches appear in your feed with the terms that earned the score, and you can turn on email alerts for fresh ones."
  },
  {
    q: "How does resume tailoring work?",
    a: "For a given role, the assistant rewrites and re-orders your existing bullets to align with the job's keywords — without inventing experience — and returns a list of every change plus the keywords it matched. You review it before using it, and tailored versions are saved per company."
  },
  {
    q: "I'm on OPT or need sponsorship — does it help?",
    a: "Yes. Your work-authorization status and sponsorship need are stored on your profile, used to pre-fill screening answers, and used to filter out roles that explicitly won't sponsor."
  },
  {
    q: "Is auto-apply actually hands-off?",
    a: "It's consent-first. Auto-apply requires explicit consent, respects daily and monthly caps, and defaults to per-application approval and dry-run. The headless submit engine is experimental and never touches boards that prohibit automation."
  },
  {
    q: "Is there a free plan?",
    a: "Yes — the Free tier includes resume-based matching and the assistant. Paid tiers (Starter, Pro, Power) add auto-apply with higher monthly application volumes."
  }
];

export default function HomePage() {
  const [stage, setStage] = useState<Stage>("find");
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const active = STAGES.find((s) => s.key === stage)!;

  useEffect(() => {
    // The landing page is always light; the theme toggle lives in the dashboard.
    document.documentElement.removeAttribute("data-mode");
    document.documentElement.setAttribute("data-theme", "default");
  }, []);

  return (
    <main className="landing">
      <header className="lp-nav">
        <div className="lp-nav-inner">
          <a className="lp-logo" href="/">AIapply.ai</a>
          <nav className="lp-links">
            <a href="#how">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="lp-nav-cta">
            <Link href="/login" className="lp-btn ghost">Log in</Link>
            <Link href="/login" className="lp-btn solid">Sign up</Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="lp-hero">
        <span className="lp-badge">Resume-aware · consent-first</span>
        <h1>Be first to every job that fits you.</h1>
        <div className="lp-hero-row">
          <p className="lp-hero-sub">
            AIapply.ai watches public career boards across Greenhouse, Lever, and Ashby,
            scores each new role against your resume, and tailors your application — with
            every change shown to you before anything goes out.
          </p>
          <div className="lp-hero-actions">
            <Link href="/login" className="lp-btn solid lg">Get started</Link>
            <a href="#how" className="lp-btn outline lg">See how it works</a>
            <span className="lp-fineprint">Free to start. No card required.</span>
          </div>
        </div>
        <div className="lp-available">
          <span>Also available on</span>
          <b>Web</b>
          <b>Chrome extension</b>
          <b>MCP / CLI</b>
        </div>
      </section>

      {/* Sources */}
      <section className="lp-sources">
        <p className="lp-eyebrow">Sources roles directly from</p>
        <div className="lp-source-row">
          <span>Greenhouse</span>
          <span>Lever</span>
          <span>Ashby</span>
          <span className="muted">+ your LinkedIn / Indeed CSV imports</span>
        </div>
      </section>

      {/* Pipeline */}
      <section className="lp-section" id="how">
        <p className="lp-eyebrow">The pipeline</p>
        <h2>Four stages. One agent.</h2>
        <div className="lp-tabs">
          {STAGES.map((s, i) => (
            <button
              key={s.key}
              className={`lp-tab${stage === s.key ? " active" : ""}`}
              onClick={() => setStage(s.key)}
              type="button"
            >
              <span className="lp-tab-num">0{i + 1}</span> {s.label}
            </button>
          ))}
        </div>
        <div className="lp-stage">
          <div className="lp-stage-copy">
            <p className="lp-kicker">{active.kicker}</p>
            <h3>{active.title}</h3>
            <p className="lp-body">{active.body}</p>
          </div>
          <ul className="lp-stage-points">
            {active.points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      </section>

      {/* Surfaces */}
      <section className="lp-section">
        <p className="lp-eyebrow">Wherever you work</p>
        <h2>One agent. Any surface.</h2>
        <div className="lp-surface-grid">
          {SURFACES.map((s) => (
            <article key={s.tag} className="lp-surface">
              <p className="lp-tag">{s.tag}</p>
              <h3>{s.title}</h3>
              <p className="lp-body">{s.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="lp-section" id="pricing">
        <p className="lp-eyebrow">Pricing</p>
        <h2>Pay for applications, not the tool.</h2>
        <p className="lp-body lp-narrow">Every paid tier is the full product — they differ only by monthly application volume.</p>
        <div className="lp-price-grid">
          {PLANS.map((p) => (
            <article key={p.name} className={`lp-price${p.featured ? " featured" : ""}`}>
              {p.featured && <span className="lp-pop">Most popular</span>}
              <h3>{p.name}</h3>
              <p className="lp-price-amt">
                {p.price}
                {p.price !== "$0" && <span> / mo</span>}
              </p>
              <p className="lp-body">{p.blurb}</p>
              <p className="lp-apps">
                <strong>{p.apps}</strong>
                {p.apps !== "Matching only" && <span> applications / 30 days</span>}
              </p>
              <Link href="/login" className={`lp-btn ${p.featured ? "invert" : "solid"} full`}>
                {p.cta}
              </Link>
            </article>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="lp-section" id="faq">
        <p className="lp-eyebrow">Frequently asked</p>
        <h2>What people ask before signing up.</h2>
        <div className="lp-faq">
          {FAQS.map((f, i) => (
            <div key={f.q} className={`lp-faq-item${openFaq === i ? " open" : ""}`}>
              <button
                type="button"
                className="lp-faq-q"
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
                aria-expanded={openFaq === i}
              >
                <span>{f.q}</span>
                <span className="lp-faq-sign">{openFaq === i ? "−" : "+"}</span>
              </button>
              {openFaq === i && <p className="lp-faq-a">{f.a}</p>}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="lp-cta">
        <h2>Get your next applications off your plate.</h2>
        <Link href="/login" className="lp-btn solid lg">Get started</Link>
      </section>

      <footer className="lp-footer">
        <div className="lp-footer-top">
          <a className="lp-logo" href="/">AIapply.ai</a>
          <nav className="lp-links">
            <a href="#how">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
            <Link href="/login">Log in</Link>
          </nav>
        </div>
        <p className="lp-copy">A transparent agent for job applications. © 2026 AIapply.ai</p>
      </footer>
    </main>
  );
}
