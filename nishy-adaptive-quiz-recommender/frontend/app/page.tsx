import Link from "next/link";
import AppHeader from "@/components/ui/AppHeader";
import { ArrowRightIcon, FileTextIcon, HelpCircleIcon, BarChartIcon } from "@/components/ui/Icons";

export default function HomePage() {
  return (
    <main className="landing min-h-screen">
      <AppHeader home />
      <section className="editorial-hero">
        <h1 className="animate-slide-up">Study with <span className="hero-underline">purpose.</span><br />Learn with<br className="hidden lg:block" /> evidence.</h1>
        <div className="hero-intro animate-fade-in">
          <p>Better understanding starts with better questions. Turn your study material into thoughtful practice that grows with you.</p>
          <Link href="/upload" id="cta-start-quiz" className="btn-primary mt-8">Start adaptive quiz <ArrowRightIcon /></Link>
        </div>
      </section>
      <section className="featured-learning" aria-labelledby="learning-heading">
        <div className="featured-copy">
          <p className="section-label mb-6">A more thoughtful way to learn</p>
          <h2 id="learning-heading">Make room for<br />deeper thinking.</h2>
          <p className="featured-description">Start with what you know. Connect ideas, work through a challenge, and use carefully paced hints to find your own way forward.</p>
          <a href="#how-it-works" className="editorial-link mt-8">Explore the process <ArrowRightIcon /></a>
        </div>
        <div className="learning-illustration" aria-hidden="true">
          <svg viewBox="0 0 480 400" fill="none">
            <path d="M100 314C138 273 155 209 225 83M383 314C342 254 312 168 244 65" stroke="currentColor" strokeWidth="2" />
            <path d="M124 275C184 311 307 311 360 275M151 226C204 196 278 196 332 226M178 177C218 202 271 202 306 177M204 128C229 110 256 110 280 128M224 84H252M90 335H390" stroke="currentColor" strokeWidth="2" />
            <circle cx="225" cy="83" r="7" fill="currentColor" /><circle cx="151" cy="226" r="5" fill="currentColor" /><circle cx="360" cy="275" r="5" fill="currentColor" />
            <circle cx="240" cy="199" r="158" stroke="currentColor" strokeOpacity=".2" />
            <path d="M67 116L77 121L67 126L62 136L57 126L47 121L57 116L62 106Z" fill="currentColor" />
          </svg>
        </div>
      </section>
      <section id="how-it-works" className="editorial-section">
        <div className="editorial-section-heading"><h2>From your notes to new understanding.</h2><p className="section-label">The process</p></div>
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { icon: <FileTextIcon />, number: "01", title: "Bring your material", text: "Choose your notes, upload a document, or start with a Biology topic. Your material sets the direction." },
            { icon: <HelpCircleIcon />, number: "02", title: "Think it through", text: "Work through direct recall or more demanding questions. Hints guide your reasoning without giving the answer away." },
            { icon: <BarChartIcon />, number: "03", title: "Build on what you learn", text: "Review your performance, revisit useful study notes, and explore relevant YouTube videos." },
          ].map(item => <article key={item.number} className="process-item">
            <div className="flex items-center justify-between mb-9"><span className="section-label">{item.number}</span>{item.icon}</div>
            <h3>{item.title}</h3><p>{item.text}</p>
          </article>)}
        </div>
      </section>
      <section id="features" className="editorial-section">
        <div className="editorial-section-heading"><h2>Practice, at your pace.</h2><p className="section-label">Designed for understanding</p></div>
        <div className="grid md:grid-cols-2 gap-5">
          <article className="feature-panel"><span className="section-label">Adaptive questions</span><h3>A challenge that responds to you.</h3><p>Choose Easy, Medium, or Hard. Adaptive mode adjusts the next question as you work through your answers.</p></article>
          <article className="feature-panel feature-panel-clay"><span className="section-label">Thoughtful guidance</span><h3>Keep the thinking yours.</h3><p>Move from a demanding reasoning prompt to a gentler scaffold, then a reminder to revisit your own notes.</p></article>
        </div>
      </section>
      <section className="home-closing"><h2>What will you understand next?</h2><Link href="/upload" id="cta-banner-start" className="btn-primary">Begin a quiz <ArrowRightIcon /></Link></section>
      <footer className="app-footer"><span className="app-wordmark">AdaptiveIQ</span><span>Nishy ? Adaptive learning</span><Link href="/upload" className="nav-link">Start learning</Link></footer>
    </main>
  );
}
