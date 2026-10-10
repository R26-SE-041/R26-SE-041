import Link from "next/link";
import {
  FileTextIcon,
  ZapIcon,
  HelpCircleIcon,
  BarChartIcon,
  TargetIcon,
  TrendingUpIcon,
  LayersIcon,
  CpuIcon,
  ListIcon,
  ClipboardIcon,
  ArrowRightIcon,
} from "@/components/ui/Icons";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-[18px] py-5 max-w-[1040px] mx-auto w-full border-b border-stone-900/10">
        <div className="flex items-center gap-2.5">
          <div className="brand-mark w-8 h-8 rounded-lg">
            <span className="font-bold text-sm">AQ</span>
          </div>
          <span className="font-bold text-lg tracking-tight">
            Adaptive<span className="text-gradient">IQ</span>
          </span>
        </div>
        <div className="hidden md:flex items-center gap-6 text-sm text-stone-900/60">
          <a href="#how-it-works" className="hover:text-stone-900 transition-colors">How it works</a>
          <a href="#features" className="hover:text-stone-900 transition-colors">Features</a>
        </div>
        <Link href="/upload" className="btn-primary flex items-center gap-2 text-sm px-5 py-2.5">
          Start Quiz <ArrowRightIcon />
        </Link>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-[18px] pt-20 pb-24 relative">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 60% 42% at 50% 10%, rgba(216,101,59,0.10) 0%, transparent 72%)",
          }}
          aria-hidden="true"
        />

        {/* Badge */}
        <div className="animate-fade-in mb-6">
          <span className="badge-violet text-sm px-4 py-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-600" />
            Source-grounded adaptive assessment
          </span>
        </div>

        {/* Heading */}
        <h1 className="animate-slide-up text-5xl md:text-[58px] font-bold tracking-[-2px] leading-[1.08] md:leading-[63px] mb-7 max-w-4xl text-stone-800">
          Study with purpose.
          <br />
          <span className="text-gradient italic">Learn with evidence.</span>
        </h1>

        <p className="animate-fade-in text-lg md:text-xl text-stone-900/60 max-w-2xl mb-10 leading-relaxed">
          Turn your own notes into structured, adaptive assessments. Every question is grounded
          in your material and adjusts thoughtfully as you progress.
        </p>

        {/* CTA Buttons */}
        <div className="animate-fade-in flex flex-col sm:flex-row gap-4">
          <Link href="/upload" id="cta-start-quiz" className="btn-primary text-base px-8 py-4">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Start Adaptive Quiz
          </Link>
          <a href="#how-it-works" className="btn-secondary text-base px-8 py-4">
            See how it works
          </a>
        </div>

        {/* Stats row */}
        <div className="animate-fade-in mt-16 grid grid-cols-3 gap-0 max-w-xl w-full mx-auto text-center editorial-rule py-5">
          {[
            { val: "7B", label: "Parameter LLM" },
            { val: "RAG", label: "Grounded Questions" },
            { val: "IRT", label: "Adaptive Engine" },
          ].map((s) => (
            <div key={s.val} className="px-4 border-r border-stone-900/10 last:border-r-0">
              <div className="text-2xl font-semibold text-orange-700 font-serif">{s.val}</div>
              <div className="text-xs text-stone-500 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="py-24 px-[18px] max-w-[1040px] mx-auto w-full">
        <div className="text-center mb-16">
          <p className="section-label mb-3">The Process</p>
          <h2 className="text-3xl md:text-4xl font-bold">How AdaptiveIQ works</h2>
        </div>

        <div className="grid md:grid-cols-4 gap-4">
          {[
            {
              step: "01",
              icon: <FileTextIcon className="w-8 h-8" />,
              title: "Upload Documents",
              desc: "Use PDF, DOCX, PPTX, TXT, JPG, or PNG study material.",
            },
            {
              step: "02",
              icon: <ZapIcon className="w-8 h-8" />,
              title: "AI Ingestion",
              desc: "LangGraph agents extract topics and build a knowledge graph.",
            },
            {
              step: "03",
              icon: <HelpCircleIcon className="w-8 h-8" />,
              title: "Adaptive Questions",
              desc: "Qwen2.5-7B generates Bloom's-level MCQs grounded in your docs.",
            },
            {
              step: "04",
              icon: <BarChartIcon className="w-8 h-8" />,
              title: "Instant Feedback",
              desc: "See your performance, weak topics, and difficulty progression.",
            },
          ].map((item) => (
            <div
              key={item.step}
              className="glass-card p-[22px] relative overflow-hidden"
            >
              <div className="text-xs font-bold text-stone-400 mb-4 tracking-widest">STEP {item.step}</div>
              <div className="mb-4 text-orange-700 w-12 h-12 rounded-xl bg-orange-50 border border-orange-900/10 flex items-center justify-center">{item.icon}</div>
              <h3 className="font-bold text-stone-900 mb-2">{item.title}</h3>
              <p className="text-sm text-stone-500 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-[18px] max-w-[1040px] mx-auto w-full">
        <div className="text-center mb-16">
          <p className="section-label mb-3">Features</p>
          <h2 className="text-3xl md:text-4xl font-bold">
            Research-grade <span className="text-gradient">adaptive learning</span>
          </h2>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[
            {
              icon: <TargetIcon className="w-7 h-7" />,
              title: "RAG-Grounded Questions",
              desc: "Every question is verified against your uploaded material using cosine similarity. Hallucinations are detected and rejected.",
              badge: "Research Metric",
              badgeType: "badge-violet",
            },
            {
              icon: <TrendingUpIcon className="w-7 h-7" />,
              title: "Real-time Difficulty Adaptation",
              desc: "Strong performance keeps questions challenging. More attempts gradually reduce the next question's difficulty.",
              badge: "IRT Model",
              badgeType: "badge-cyan",
            },
            {
              icon: <LayersIcon className="w-7 h-7" />,
              title: "Bloom's Taxonomy Mapping",
              desc: "Questions span recall, application, and analysis. The system tracks coverage across cognitive levels.",
              badge: "6 Levels",
              badgeType: "badge-green",
            },
            {
              icon: <CpuIcon className="w-7 h-7" />,
              title: "Multi-Agent LangGraph",
              desc: "7 specialized agents: Ingestion, Knowledge, Quiz, Evaluation, Adaptive, Recommendation, Analytics.",
              badge: "7 Agents",
              badgeType: "badge-violet",
            },
            {
              icon: <ZapIcon className="w-7 h-7" />,
              title: "Qwen2.5-7B on Modal.com",
              desc: "The open-source LLM runs serverlessly on GPU with a reproducible research setup.",
              badge: "Open Source",
              badgeType: "badge-cyan",
            },
            {
              icon: <ListIcon className="w-7 h-7" />,
              title: "MCQ + Structured + Essay",
              desc: "Choose your exam format. All types support adaptive difficulty and grounding verification.",
              badge: "3 Types",
              badgeType: "badge-green",
            },
          ].map((f) => (
            <div key={f.title} className="glass-card-hover p-[22px]">
              <div className="mb-4 text-orange-700">{f.icon}</div>
              <div className="flex items-start justify-between gap-2 mb-3">
                <h3 className="font-bold text-stone-900 text-lg leading-tight">{f.title}</h3>
                <span className={`${f.badgeType} shrink-0 mt-0.5`}>{f.badge}</span>
              </div>
              <p className="text-sm text-stone-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Banner */}
      <section className="py-20 px-6 max-w-4xl mx-auto w-full text-center">
        <div className="glass-card p-[22px] md:p-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready to test your knowledge?
          </h2>
          <p className="text-stone-900/60 mb-8 text-lg">Upload your study material and start your first adaptive quiz in minutes.</p>
          <Link href="/upload" id="cta-banner-start" className="btn-primary inline-flex items-center gap-2 text-base px-10 py-4">
            Get Started Free <ArrowRightIcon />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 text-center text-stone-400 text-sm border-t border-orange-900/10">
        AdaptiveIQ | MSc Research Project | Adaptive AI Assessment Platform | Built with LangGraph + Qwen2.5 + Next.js
      </footer>
    </main>
  );
}
