"use client";

import { useEffect, useState } from "react";

type Theme = "default" | "bw";
const STORAGE_KEY = "aiapply-theme";

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
      aria-label="Toggle black and white theme"
      title="Toggle black & white theme"
    >
      {theme === "bw" ? "Color theme" : "Black & White"}
    </button>
  );
}
