"use client";

import React, { useEffect, useRef, useState, type CSSProperties } from "react";

/** Shared toolkit navigation; never reads or changes learning/session state. */
export default function ToolkitNavigation({ componentName, background = "var(--background, #f0eee6)", color = "var(--text, #141413)", border = "var(--border, #d6d3c9)" }: {
  componentName: string; background?: string; color?: string; border?: string;
}) {
  const [showTop, setShowTop] = useState(false);
  const scroller = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let frame = 0;
    const pageScroller = () => document.scrollingElement as HTMLElement | null;
    const update = () => {
      frame = 0;
      if (!scroller.current?.isConnected) scroller.current = pageScroller();
      const target = scroller.current;
      setShowTop(Boolean(target && target.scrollTop > 500 && target.scrollHeight - target.clientHeight > 600));
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(update); };
    const onScroll = (event: Event) => {
      const target = event.target === document ? pageScroller() : event.target;
      // Include full-size React Native web workspaces; leave small panels alone.
      if (!(target instanceof HTMLElement)) return;
      if (target !== pageScroller() && (target.clientHeight < window.innerHeight * .45 || target.clientWidth < window.innerWidth * .45)) return;
      scroller.current = target;
      schedule();
    };
    document.addEventListener("scroll", onScroll, { capture: true, passive: true });
    window.addEventListener("resize", schedule);
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    update();
    return () => {
      document.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", schedule);
      observer.disconnect();
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  const backToTop = () => {
    const target = scroller.current;
    if (!target?.isConnected) { setShowTop(false); return; }
    target.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    document.querySelector<HTMLAnchorElement>("a.lx-toolkit-home")?.focus({ preventScroll: true });
  };

  return <div style={{ display: "contents", "--lx-bg": background, "--lx-ink": color, "--lx-border": border } as CSSProperties}>
    <style>{`
      .lx-toolkit-bar { box-sizing: border-box; flex-shrink: 0; display: flex; align-items: center; gap: 20px; min-height: 48px; padding: 10px 24px; background: var(--lx-bg); color: var(--lx-ink); border-bottom: 1px solid var(--lx-border); font-family: Arial, Helvetica, sans-serif; }
      .lx-toolkit-home { cursor: pointer; user-select: none; -webkit-user-select: none; position: relative; display: inline-flex; align-items: center; color: inherit; text-decoration: none; font-size: 18px; line-height: 1; font-weight: 800; letter-spacing: -.6px; }
      .lx-toolkit-home::after { content: ''; position: absolute; left: 0; right: 0; bottom: -7px; height: 2px; background: #c6613f; transform: scaleX(0); transform-origin: left; transition: transform 320ms cubic-bezier(.2,.65,.3,1); }
      .lx-toolkit-x { display: inline-block; font-weight: 400; margin-left: 1px; transform: skew(-11deg); transition: transform 320ms cubic-bezier(.2,.65,.3,1), color 220ms ease; }
      .lx-toolkit-home:is(:hover, :focus-visible)::after { transform: scaleX(1); }
      .lx-toolkit-home:is(:hover, :focus-visible) .lx-toolkit-x { color: #c6613f; transform: translate(3px,-2px) rotate(12deg) skew(-11deg); }
      .lx-toolkit-component { border-left: 1px solid var(--lx-border); padding-left: 20px; font-size: 12px; line-height: 1.4; letter-spacing: 0; }
      .lx-back-top { position: fixed; z-index: 120; right: 20px; bottom: calc(88px + env(safe-area-inset-bottom, 0px)); min-height: 44px; padding: 10px 14px; border: 1px solid var(--lx-border); border-radius: 24px; color: var(--lx-ink); background: var(--lx-bg); box-shadow: 0 3px 16px #00000018; font: 13px/1.4 Arial, Helvetica, sans-serif; cursor: pointer; }
      .lx-toolkit-home:focus-visible, .lx-back-top:focus-visible { outline: 2px solid #c6613f; outline-offset: 4px; }
      .lx-back-top:hover { border-color: #c6613f; }
      @media(max-width: 480px) { .lx-toolkit-bar { padding-inline: 20px; gap: 14px; } .lx-toolkit-component { padding-left: 14px; } }
      @media(prefers-reduced-motion: reduce) { .lx-toolkit-home::after, .lx-toolkit-x { transition: none; } .lx-toolkit-home:is(:hover, :focus-visible) .lx-toolkit-x { transform: skew(-11deg); } }
    `}</style>
    {showTop && <button type="button" className="lx-back-top" onClick={backToTop} aria-label="Back to top">Back to top <span aria-hidden="true">↑</span></button>}
  </div>;
}
