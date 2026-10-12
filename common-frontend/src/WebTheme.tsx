import React from 'react';
import { Platform } from 'react-native';

export default function WebTheme() {
  if (Platform.OS !== 'web') return null;
  return <style>{`
    body { background: #FAF9F5; }
    [data-workspace], input, textarea, button { font-family: "Segoe UI", Arial, sans-serif; }
    button, input, textarea, [role="button"] { -webkit-tap-highlight-color: transparent; }
    [data-workspace] [role="button"], [data-workspace] [role="tab"] { transition: background-color 160ms ease, border-color 160ms ease, opacity 160ms ease; }
    [role="tab"]:focus-visible, [role="button"]:focus-visible, input:focus-visible, textarea:focus-visible, audio:focus-visible {
      outline: 2px solid #C96442; outline-offset: 3px;
    }
    input[type="file"]::file-selector-button {
      font: inherit; color: #141413; background: #FFFFFF; border: 1px solid #E4E2D9;
      border-radius: 6px; padding: 9px 13px; margin-right: 14px; cursor: pointer;
    }
    [data-page-enter] { animation: workspace-enter 220ms ease-out both; }
    @keyframes workspace-enter { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
    @media (prefers-reduced-motion: reduce) {
      [data-workspace] *, [data-page-enter] { animation: none !important; transition: none !important; }
    }
  `}</style>;
}
