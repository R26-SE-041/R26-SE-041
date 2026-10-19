// Reference: https://www.anthropic.com/ and its published ant-brand stylesheet.
// The official web fonts are referenced from their public CDN, with local fallbacks.
export const editorialWebStyles = `
@font-face{font-family:'Anthropic Sans';src:url('https://cdn.prod.website-files.com/67ce28cfec624e2b733f8a52/69971a00a3295036497e1a28_AnthropicSans-Roman-Web.woff2') format('woff2');font-style:normal;font-weight:300 800;font-display:swap}
@font-face{font-family:'Anthropic Serif';src:url('https://cdn.prod.website-files.com/67ce28cfec624e2b733f8a52/69971a1551eb6cda0d656e8a_AnthropicSerif-Roman-Web.woff2') format('woff2');font-style:normal;font-weight:300 800;font-display:swap}
@font-face{font-family:'Anthropic Mono';src:url('https://cdn.prod.website-files.com/67ce28cfec624e2b733f8a52/69971a2e55d24d61bc045b1a_AnthropicMono-Roman-Web.woff2') format('woff2');font-style:normal;font-weight:300 800;font-display:swap}
html,body,#root{background:#f0eee6;color:#141413}
body{font-family:'Anthropic Sans',Arial,sans-serif;-webkit-font-smoothing:antialiased}
::selection{background:#ebdbbc;color:#141413}
[role=button],[role=link],[role=tab]{transition:background-color .2s ease,color .2s ease,border-color .2s ease,opacity .2s ease,transform .2s ease}
[role=button]:focus-visible,[role=link]:focus-visible,[role=tab]:focus-visible{outline:2px solid #c6613f;outline-offset:5px}
#site-header [role=button]:hover{opacity:.68}
#process-button:not([aria-disabled=true]):hover{background-color:#3d3d3a!important}
#image-dropzone:hover{background-color:#e8e6dc!important}
#hero-copy{animation:editorial-reveal .7s cubic-bezier(.2,.7,.2,1) both}
#hero-intro{animation:editorial-reveal .7s .1s cubic-bezier(.2,.7,.2,1) both}
#document-workspace{animation:editorial-reveal .8s .15s cubic-bezier(.2,.7,.2,1) both}
#capability-cards [role=button]:hover{transform:translateY(-4px)}
@keyframes editorial-reveal{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
`;
