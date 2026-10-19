import React from "react";

/** Compact version of the shared brand for dialogs that cover the page header. */
export default function ToolkitBrand() {
  return <a className="lx-toolkit-home" href="https://biolearnx-dashboard.vercel.app/" draggable={false}
    aria-label="LearnX home — all learning tools"
    style={{ color: "#141413", cursor: "pointer", userSelect: "none", WebkitUserSelect: "none", fontFamily: "Arial, Helvetica, sans-serif" }}>
    Learn<span className="lx-toolkit-x">X</span>
  </a>;
}
