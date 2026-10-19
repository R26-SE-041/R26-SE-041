// Reference: anthropic.com (official homepage, inspected 18 October 2026).
// Arial and Georgia are its declared fallback families; custom brand fonts are not bundled.
export const dashboardCss = `
  :root { color-scheme: light; }
  html { scroll-behavior: smooth; scroll-padding-top: 110px; }
  body { margin: 0; background: #f0eee6; overflow: visible; }
  #root { display: block; height: auto; min-height: 100vh; }
  .bio-site { --paper: #f0eee6; --ivory: #faf9f5; --ink: #141413; --muted: #686760; --line: #d6d3c9; --clay: #c6613f; --serif: Georgia, 'Times New Roman', serif; --sans: Arial, Helvetica, sans-serif; width: 100%; min-height: 100vh; color: var(--ink); background: var(--paper); font: 16px/1.5 var(--sans); -webkit-font-smoothing: antialiased; }
  .bio-site *, .bio-site *::before, .bio-site *::after { box-sizing: border-box; }
  .bio-site h1, .bio-site h2, .bio-site h3, .bio-site p { margin: 0; }
  .bio-site a { color: inherit; text-decoration: none; text-underline-offset: .12em; }
  .bio-site button, .bio-site input { font: inherit; }
  .bio-site button, .bio-site a { -webkit-tap-highlight-color: transparent; }
  .bio-site button { cursor: pointer; }
  .bio-site svg { flex-shrink: 0; }
  .bio-site ::selection { background: #e3bca9; color: #141413; }
  .bio-site :focus-visible { outline: 2px solid var(--clay); outline-offset: 6px; }
  .skip-link { position: fixed; z-index: 100; left: 24px; top: -100px; background: var(--ink); color: var(--ivory) !important; padding: 12px 20px; border-radius: 5px; }
  .skip-link:focus { top: 16px; }
  .page-width, .header-inner { width: min(100% - 112px, 1440px); margin-inline: auto; }
  .site-header { position: sticky; top: 0; z-index: 20; background: #f0eee6f5; backdrop-filter: blur(12px); }
  .header-inner { display: flex; justify-content: space-between; align-items: center; min-height: 92px; gap: 40px; }
  .wordmark { cursor: pointer; user-select: none; -webkit-user-select: none; position: relative; font-family: var(--sans); font-size: 26px; line-height: 1; font-weight: 800; letter-spacing: -.9px; display: inline-flex; align-items: center; }
  .wordmark::after { content: ''; position: absolute; left: 0; right: 0; bottom: -7px; height: 2px; background: var(--clay); transform: scaleX(0); transform-origin: left; transition: transform 320ms cubic-bezier(.2,.65,.3,1); }
  .wordmark-x { display: inline-block; font-weight: 400; margin-left: 1px; transform: skew(-11deg); transition: transform 320ms cubic-bezier(.2,.65,.3,1), color 220ms ease; }
  .wordmark:is(:hover, :focus-visible)::after { transform: scaleX(1); }
  .wordmark:is(:hover, :focus-visible) .wordmark-x { color: var(--clay); transform: translate(3px,-2px) rotate(12deg) skew(-11deg); }
  .footer-grid .wordmark:hover { text-decoration: none; }
  @media(prefers-reduced-motion:reduce) { .wordmark:is(:hover, :focus-visible) .wordmark-x { transform: skew(-11deg); } }
  .header-nav { display: flex; align-items: center; gap: 32px; }
  .header-nav > a { font-size: 15px; display: inline-flex; align-items: center; gap: 6px; }
  .header-nav > a:not(.button):hover { text-decoration: underline; }
  .header-nav > a > svg { width: 14px; height: 14px; }
  .button { display: inline-flex; align-items: center; justify-content: space-between; gap: 24px; padding: 13px 19px; font-size: 15px; line-height: 1.35; border: 1px solid transparent; border-radius: 7px; font-family: var(--sans); transition: background 180ms ease, color 180ms ease, border-color 180ms ease; }
  .button-dark { background: var(--ink); color: var(--ivory) !important; }
  .button-dark:hover { background: #3d3d3a; }
  .button-outline { border-color: #686760; background: transparent; }
  .button-outline:hover { background: var(--ink); border-color: var(--ink); color: var(--ivory); }
  .menu-toggle { display: none; }
  .introduction { padding-block: 110px 108px; display: grid; grid-template-columns: 1.2fr 1fr; align-items: center; gap: 80px; }
  .eyebrow { display: block; font: 11px/1.5 var(--sans); letter-spacing: 1.1px; text-transform: uppercase; }
  .intro-eyebrow { margin-bottom: 24px !important; color: #686760; }
  .introduction h1 { font-size: clamp(46px, 4.6vw, 72px); line-height: 1.04; font-weight: 700; letter-spacing: -2.6px; }
  .introduction h1 a { text-decoration: underline; text-decoration-thickness: .065em; text-underline-offset: .09em; transition: color 160ms; }
  .introduction h1 a:hover { color: var(--clay); }
  .intro-copy { padding-top: 29px; }
  .intro-copy > p { font: 28px/1.28 var(--serif); letter-spacing: -.5px; max-width: 490px; }
  .project-caption { display: block; margin-top: 24px; font-size: 12px; color: var(--muted); }
  .feature-panel { display: grid; grid-template-columns: 1fr 1fr; min-height: 470px; background: var(--ivory); border-radius: 24px; overflow: hidden; }
  .feature-copy { padding: 60px 20px 60px 56px; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; }
  .feature-copy > .eyebrow { color: var(--muted); }
  .feature-copy h2 { font: 46px/1.1 var(--serif); letter-spacing: -1.4px; margin-block: 24px; }
  .feature-copy p { max-width: 390px; font-size: 16px; line-height: 1.6; color: #56554e; }
  .feature-copy .button { margin-top: 30px; }
  .feature-art { position: relative; display: flex; align-items: center; justify-content: center; flex-direction: column; background: #e3dacc; padding: 46px 32px; color: #3d3d3a; }
  .figure-label { align-self: flex-start; font-size: 10px; letter-spacing: 1.4px; color: #686155; }
  .biology-drawing { width: 100%; max-width: 510px; height: auto; margin: 30px auto 20px; }
  .figure-caption { font: italic 16px/1.4 var(--serif); color: #686155; }
  .toolkit { padding-block: 0 90px; }
  .section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 40px; }
  .section-heading .eyebrow { color: var(--muted); margin-bottom: 14px; }
  .section-heading h2 { font-size: 28px; font-weight: 600; line-height: 1.25; letter-spacing: -.7px; }
  .tool-search { display: flex; align-items: center; gap: 10px; width: 230px; border-bottom: 1px solid #87867f; padding: 10px 0; color: var(--muted); flex-shrink: 0; }
  .tool-search input { border: 0; background: transparent; width: 100%; min-width: 0; font-size: 13px; color: var(--ink); outline: none !important; border-radius: 0; }
  .tool-search:focus-within { border-color: var(--clay); box-shadow: 0 1px 0 var(--clay); }
  .tool-search input::-webkit-search-cancel-button { display: none; }
  .tool-search button { background: none; border: 0; color: var(--muted); font-size: 20px; padding: 0 3px; line-height: 1; }
  .search-result-count { color: var(--muted); font-size: 13px; margin-block: 18px 32px !important; }
  .tool-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); grid-auto-rows: 1fr; gap: 24px; }
  .tool-card { background: var(--ivory); border-radius: 12px; display: flex; flex-direction: column; padding: 27px 32px 0; transition: background 220ms ease; overflow: hidden; }
  .tool-card:hover { background: #e9e6dc; }
  .card-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; color: #686760; }
  .card-top .eyebrow { font-size: 10px; letter-spacing: .8px; }
  .card-top > svg { color: var(--ink); transition: transform 200ms; }
  .tool-card:hover .card-top > svg { transform: translate(2px,-2px); }
  .card-illustration { height: 225px; display: flex; justify-content: center; align-items: center; color: #7e6955; }
  .tool-drawing { width: 100%; height: 100%; max-width: 340px; }
  .tool-audio .card-illustration { color: #a4563c; }
  .tool-quiz .card-illustration { color: #74715c; }
  .tool-notes .card-illustration { color: #656c70; }
  .card-content h3 { font-size: 26px; font-weight: 600; letter-spacing: -.5px; margin-bottom: 12px; }
  .card-content > p { font-size: 16px; line-height: 1.6; color: #56554e; max-width: 510px; }
  .capabilities { display: flex; flex-wrap: wrap; gap: 7px 18px; padding: 0; margin: 23px 0 26px; list-style: none; color: var(--muted); font-size: 11px; }
  .capabilities li { display: flex; align-items: center; gap: 7px; }
  .capabilities li::before { content: ''; width: 3px; height: 3px; border-radius: 50%; background: #87867f; }
  .card-bottom { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-top: 1px solid var(--line); padding-block: 18px; margin-top: auto; }
  .card-bottom > span { display: flex; align-items: center; gap: 10px; font-size: 13px; }
  .card-bottom svg { width: 15px; height: 15px; }
  .card-bottom small { font-size: 11px; color: var(--muted); }
  .account-note { display: flex; justify-content: center; align-items: baseline; gap: 9px; color: var(--muted); font-size: 12px; margin-top: 24px !important; }
  .empty-state { border-block: 1px solid var(--line); padding: 65px 20px; text-align: center; }
  .empty-state h3 { font-size: 24px; font-weight: 500; overflow-wrap: anywhere; }
  .empty-state p { color: var(--muted); margin: 15px 0 25px; }
  .approach { background: #e3dacc; padding-block: 90px; }
  .approach-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 100px; align-items: start; }
  .approach h2 { font: 46px/1.12 var(--serif); letter-spacing: -1.4px; margin-block: 26px; }
  .approach-grid > div > p { max-width: 400px; color: #56554e; font-size: 16px; line-height: 1.65; }
  .journey-list > a { display: flex; align-items: flex-start; gap: 18px; border-top: 1px solid #bab1a3; padding: 23px 0; transition: color 180ms; }
  .journey-list > a:last-child { border-bottom: 1px solid #bab1a3; }
  .journey-list > a:hover { color: #a34e33; }
  .journey-number { font-size: 11px; color: #686155; padding-top: 4px; }
  .journey-list h3 { font-size: 17px; font-weight: 500; line-height: 1.35; }
  .journey-list p { font-size: 13px; color: #686155; margin-top: 7px; line-height: 1.5; }
  .journey-list > a > svg { margin-left: auto; width: 17px; height: 17px; }
  .closing { padding-block: 110px; text-align: center; }
  .closing > .eyebrow { color: var(--muted); }
  .closing h2 { font: 52px/1.1 var(--serif); letter-spacing: -1.5px; margin: 24px auto 20px; max-width: 750px; }
  .closing p { font-size: 16px; color: var(--muted); }
  .closing .button { margin-top: 30px; }
  .site-footer { background: var(--ink); color: var(--ivory); padding-top: 70px; }
  .footer-grid { display: grid; grid-template-columns: 1.4fr 1fr .9fr 1fr; gap: 56px; padding-bottom: 80px; }
  .footer-intro > p { font: 20px/1.4 var(--serif); color: #c4c1b7; margin-top: 25px; }
  .footer-grid h2 { font-size: 14px; font-weight: 600; margin-bottom: 21px; }
  .footer-grid > div:not(.footer-intro) > a { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #d3d0c6; width: fit-content; margin-top: 12px; }
  .footer-grid a:hover, .footer-base a:hover { text-decoration: underline; }
  .footer-grid a svg { width: 12px; height: 12px; }
  .footer-project p { font-size: 13px; line-height: 1.6; color: #d3d0c6; max-width: 220px; }
  .footer-project > span { display: block; margin-top: 24px; font-size: 11px; line-height: 1.7; color: #a6a49a; }
  .footer-base { display: flex; align-items: center; justify-content: space-between; gap: 24px; border-top: 1px solid #3d3d3a; padding-block: 25px; font-size: 11px; color: #b8b5ac; }
  .will-reveal { opacity: 0; transform: translateY(16px); transition: opacity 550ms ease, transform 550ms cubic-bezier(.2,.65,.3,1); }
  .will-reveal.is-visible { opacity: 1; transform: none; }
  .introduction { animation: intro-enter 550ms ease both; }
  @keyframes intro-enter { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
  @media(min-width:1600px) { .introduction { padding-block: 130px; } .feature-panel { min-height: 510px; } }
  @media(max-width:1100px) { .page-width, .header-inner { width: calc(100% - 80px); } .header-nav { gap: 22px; } .introduction { gap: 48px; padding-block: 90px; } .introduction h1 { font-size: 50px; letter-spacing: -1.9px; } .intro-copy > p { font-size: 25px; } .feature-copy { padding: 42px 30px; } .feature-copy h2 { font-size: 38px; } .feature-panel { min-height: 430px; } .feature-art { padding-inline: 18px; } .section-heading h2 { font-size: 25px; } .approach-grid { gap: 50px; } .approach h2 { font-size: 39px; } .footer-grid { gap: 32px; grid-template-columns: 1.1fr 1fr 1fr; } .footer-project { grid-column: 2 / 4; } .footer-project p { max-width: 400px; } }
  @media(max-width:760px) { html { scroll-padding-top: 95px; } .page-width, .header-inner { width: calc(100% - 40px); } .header-inner { min-height: 76px; } .wordmark { font-size: 23px; } .menu-toggle { display: flex; flex-direction: column; justify-content: center; gap: 6px; width: 44px; height: 44px; background: transparent; border: 1px solid #d6d3c9; border-radius: 6px; padding: 11px; } .menu-toggle span { width: 20px; height: 1px; background: var(--ink); } .header-nav { display: none; position: absolute; top: 76px; left: 0; right: 0; background: var(--paper); border-bottom: 1px solid var(--line); padding: 18px 20px 24px; gap: 0; } .header-nav.is-open { display: flex; flex-direction: column; align-items: stretch; } .header-nav > a { min-height: 48px; padding-block: 12px; } .header-nav > .button { margin-top: 12px; } .introduction { grid-template-columns: 1fr; gap: 30px; padding-block: 56px 54px; } .intro-eyebrow { margin-bottom: 21px !important; font-size: 10px; } .introduction h1 { font-size: clamp(39px,7.5vw,55px); letter-spacing: -1.7px; line-height: 1.07; max-width: 600px; } .intro-copy { padding: 0; } .intro-copy > p { font-size: 25px; line-height: 1.3; max-width: 570px; } .project-caption { margin-top: 18px; font-size: 11px; } .feature-panel { grid-template-columns: 1fr; border-radius: 16px; } .feature-copy { padding: 34px 28px 38px; } .feature-copy h2 { font-size: 37px; margin-block: 20px; } .feature-copy p { font-size: 15px; max-width: 490px; } .feature-copy .button { font-size: 14px; margin-top: 25px; } .feature-art { padding: 27px; } .biology-drawing { max-width: 350px; margin-block: 12px; } .figure-caption { font-size: 15px; } .toolkit { padding-block: 65px 55px; } .section-heading { flex-direction: column; align-items: stretch; gap: 24px; } .section-heading h2 { font-size: 26px; max-width: 350px; } .tool-search { width: 100%; } .tool-search input { font-size: 14px; } .search-result-count { margin-bottom: 25px !important; font-size: 12px; } .tool-grid { grid-template-columns: 1fr; gap: 18px; } .tool-card { padding: 24px 25px 0; } .card-illustration { height: 210px; } .card-content h3 { font-size: 26px; } .card-content > p { font-size: 15px; } .capabilities { gap: 7px 13px; font-size: 10px; } .card-bottom small { font-size: 10px; } .account-note { justify-content: flex-start; align-items: flex-start; font-size: 11px; line-height: 1.6; } .approach { padding-block: 55px; } .approach-grid { grid-template-columns: 1fr; gap: 35px; } .approach h2 { font-size: 38px; margin-block: 22px; } .approach-grid > div > p { font-size: 15px; max-width: 500px; } .journey-list > a { gap: 15px; padding-block: 21px; } .journey-list h3 { font-size: 16px; } .journey-list p { font-size: 12px; } .closing { padding-block: 65px; } .closing h2 { font-size: 40px; max-width: 500px; } .closing p { font-size: 14px; } .closing .button { font-size: 14px; } .site-footer { padding-top: 45px; } .footer-grid { grid-template-columns: 1fr 1fr; gap: 37px 24px; padding-bottom: 45px; } .footer-intro { grid-column: 1 / -1; } .footer-intro > p { font-size: 19px; margin-top: 15px; } .footer-project { grid-column: 1 / -1; } .footer-grid h2 { margin-bottom: 17px; } .footer-grid > div:not(.footer-intro) > a { font-size: 12px; } .footer-base { flex-wrap: wrap; gap: 12px; padding-block: 22px; font-size: 10px; } .footer-base > span:nth-child(2) { order: 3; width: 100%; } .footer-base > a { margin-left: auto; } }
  @media(prefers-reduced-motion:reduce) { html { scroll-behavior: auto; } .bio-site *, .bio-site *::before, .bio-site *::after { animation: none !important; transition: none !important; } .will-reveal { opacity: 1; transform: none; } }
`;
