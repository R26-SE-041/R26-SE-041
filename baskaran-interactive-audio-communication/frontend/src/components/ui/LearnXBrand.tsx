/** Header branding only; study and navigation behavior stays with the page. */
export function LearnXBrand() {
  return <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10, color: 'inherit' }}>
    <span data-learnx-logo="true" style={{ fontSize: 18, lineHeight: 1, fontWeight: 700, letterSpacing: '-0.6px' }}>Learn<span data-learnx-logo-x="true">X</span></span>
    <span style={{ fontSize: 10, lineHeight: 1.2, fontWeight: 500 }}>VoiceLearn AI</span>
  </span>
}
