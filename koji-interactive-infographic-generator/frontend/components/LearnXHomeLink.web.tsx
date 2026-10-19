import React from "react";

export default function LearnXHomeLink({ color, size = 26 }: { color: string; size?: number }) {
  return <a className="lx-toolkit-home" href="https://biolearnx-dashboard.vercel.app/" draggable={false}
    aria-label="LearnX home — all learning tools"
    style={{ color, fontFamily: "Arial, Helvetica, sans-serif", fontSize: size, lineHeight: 1, fontWeight: 800, letterSpacing: -.9, cursor: "pointer", userSelect: "none", WebkitUserSelect: "none" }}>
    LEARN<span className="lx-toolkit-x">X</span>
  </a>;
}
