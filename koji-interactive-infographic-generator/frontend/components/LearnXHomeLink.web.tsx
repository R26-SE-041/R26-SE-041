import React from "react";

export default function LearnXHomeLink({ color, fontFamily }: { color: string; fontFamily?: string }) {
  return <a className="lx-toolkit-home" href="https://biolearnx-dashboard.vercel.app/" draggable={false}
    aria-label="LearnX home — all learning tools"
    style={{ color, fontFamily, fontSize: 24, fontWeight: 700, letterSpacing: -.8, cursor: "pointer", userSelect: "none", WebkitUserSelect: "none" }}>
    learn<span className="lx-toolkit-x">X</span>
  </a>;
}
