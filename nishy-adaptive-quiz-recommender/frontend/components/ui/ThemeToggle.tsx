"use client";

import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("adaptiveiq-theme");
    const useDark = saved === "dark";
    setDark(useDark);
    document.documentElement.dataset.theme = useDark ? "dark" : "light";
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    localStorage.setItem("adaptiveiq-theme", next ? "dark" : "light");
  };

  return (
    <button type="button" onClick={toggle} className="theme-toggle" aria-label={`Use ${dark ? "light" : "dark"} mode`}>
      <span aria-hidden="true">{dark ? "☀" : "☾"}</span>
      <span>{dark ? "Light" : "Dark"}</span>
    </button>
  );
}
