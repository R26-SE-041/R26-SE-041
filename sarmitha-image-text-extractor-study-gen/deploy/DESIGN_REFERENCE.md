# Frontend design reference

Reference inspected on 2026-10-16: [Anthropic's official homepage](https://www.anthropic.com/).
The published [official brand stylesheet](https://cdn.prod.website-files.com/67ce28cfec624e2b733f8a52/css/ant-brand.shared.0836b103a.min.css)
and a desktop screenshot were used to check the visual system. No other website
was used as a design reference.

The frontend retains its own Sinhala OCR identity and document workflow. Its
presentation uses the reference's typography, colors, proportions, and motion:

- Ivory medium canvas `#F0EEE6`, ivory light panels `#FAF9F5`, slate text `#141413`.
- Secondary text `#5E5D59`, fine dividers `#D1CFC5`, oat `#E3DACC`, matcha
  `#CED6BF`, and heather `#CBCADB` accents.
- Anthropic Sans for headings and controls, Anthropic Serif for editorial copy,
  and Anthropic Mono for short labels. Web fonts reference the official public
  CDN; Arial, Georgia, and monospace remain fallbacks.
- A 68 px navigation area, approximately 5.5vw desktop page gutters, a bold
  64 px desktop hero, serif supporting text, and generous vertical spacing.
- Softly rounded light panels, compact black buttons, fine rules, and simple
  original line illustrations.
- 200 ms hover/focus transitions, subtle entrance motion, visible keyboard
  focus, and a reduced-motion media query.

The upload workspace, image comparison, processing feedback, language tabs,
copy control, error states, and footer use the same system. Navigation and
calls to action scroll to real sections. Mobile navigation uses an expandable
menu, and narrow screens stack the workspace and result columns.

## Validation

The production Expo export and TypeScript check passed. Headless Chrome checks
at 1440x1100 and 390x844 confirmed that all three web fonts loaded, neither layout
overflowed horizontally, and navigation, image selection, result rendering,
Tamil/English tabs, and reset worked. Reduced-motion checking returned no
entrance animation. Result-state UI checks used a synthetic response; the
backend model pipeline had already passed live inference testing separately.

Reference screenshots and QA artifacts are in ignored `.tmp/design-reference`
and `.tmp/design-qa` directories. Production is https://sarmitha-ocr.vercel.app.
