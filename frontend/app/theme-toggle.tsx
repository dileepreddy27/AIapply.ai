"use client";

import { useEffect, useState } from "react";

type Theme = "default" | "bw";
const STORAGE_KEY = "aiapply-theme";

// Bubble dot ringed by small dots — the appearance/theme icon.
function ThemeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="3.4" r="1.5" />
      <circle cx="12" cy="20.6" r="1.5" />
      <circle cx="3.4" cy="12" r="1.5" />
      <circle cx="20.6" cy="12" r="1.5" />
      <circle cx="6" cy="6" r="1.25" />
      <circle cx="18" cy="6" r="1.25" />
      <circle cx="6" cy="18" r="1.25" />
      <circle cx="18" cy="18" r="1.25" />
    </svg>
  );
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("default");

  useEffect(() => {
    let stored: Theme | null = null;
    try {
      stored = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
    } catch {
      stored = null;
    }
    const initial: Theme = stored === "bw" ? "bw" : "default";
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
  }, []);

  function toggle() {
    const next: Theme = theme === "bw" ? "default" : "bw";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore storage errors (private mode) */
    }
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-pressed={theme === "bw"}
      aria-label="Toggle theme"
      title="Toggle theme"
    >
      <ThemeIcon />
    </button>
  );
}
