import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-button-gradient flex items-center justify-center glow-violet">
            <span className="text-white font-bold text-sm">AQ</span>
          </div>
          <span className="font-bold text-lg tracking-tight">
            Adaptive<span className="text-gradient">IQ</span>
          </span>
        </div>
        <div className="hidden md:flex items-center gap-6 text-sm text-white/60">
          <a href="#how-it-works" className="hover:text-white transition-colors">How it works</a>
          <a href="#features" className="hover:text-white transition-colors">Features</a>
        </div>
        <Link href="/upload" className="btn-primary text-sm px-5 py-2.5">
          Start Quiz →
        </Link>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-6 pt-16 pb-24 relative">
        {/* Background hero gradient */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -5%, rgba(124,58,237,0.4) 0%, transparent 70%)",
          }}
          aria-hidden="true"
        />

        {/* Badge */}
        <div className="animate-fade-in mb-6">
          <span className="badge-violet text-sm px-4 py-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse-slow" />
            Powered by Qwen2.5-7B + LangGraph
          </span>
        </div>

        {/* Heading */}
        <h1 className="animate-slide-up text-5xl md:text-7xl font-extrabold tracking-tight leading-[1.1] mb-6 max-w-4xl">
          Turn your notes into
          <br />
          <span className="text-gradient">adaptive quizzes</span>
        </h1>

        <p className="animate-fade-in text-lg md:text-xl text-white/60 max-w-2xl mb-10 leading-relaxed">
          Upload any study material — PDF, DOCX, PPTX. Our multi-agent AI extracts
          topics, generates Bloom&apos;s-level questions, and adapts difficulty to
          your answers in real-time.
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
        <div className="animate-fade-in mt-16 grid grid-cols-3 gap-8 max-w-lg mx-auto text-center">
          {[
            { val: "7B", label: "Parameter LLM" },
            { val: "RAG", label: "Grounded Questions" },
            { val: "IRT", label: "Adaptive Engine" },
          ].map((s) => (
            <div key={s.val}>
              <div className="text-2xl font-bold text-gradient">{s.val}</div>
              <div className="text-xs text-white/40 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="py-24 px-6 max-w-6xl mx-auto w-full">
        <div className="text-center mb-16">
          <p className="section-label mb-3">The Process</p>
          <h2 className="text-3xl md:text-4xl font-bold">How AdaptiveIQ works</h2>
        </div>

        <div className="grid md:grid-cols-4 gap-4">
          {[
            {
              step: "01",
              icon: "📄",
              title: "Upload Documents",
              desc: "PDF, DOCX, PPTX, TXT — any study material you have.",
              color: "from-violet-600/20 to-violet-600/5",
            },
            {
              step: "02",
              icon: "🧠",
              title: "AI Ingestion",
              desc: "LangGraph agents extract topics and build a knowledge graph.",
              color: "from-indigo-600/20 to-indigo-600/5",
            },
            {
              step: "03",
              icon: "❓",
              title: "Adaptive Questions",
              desc: "Qwen2.5-7B generates Bloom's-level MCQs grounded in your docs.",
              color: "from-cyan-600/20 to-cyan-600/5",
            },
            {
              step: "04",
              icon: "📊",
              title: "Instant Feedback",
              desc: "See your performance, weak topics, and difficulty progression.",
              color: "from-emerald-600/20 to-emerald-600/5",
            },
          ].map((item) => (
            <div
              key={item.step}
              className={`glass-card p-6 bg-gradient-to-b ${item.color} relative overflow-hidden`}
            >
              <div className="text-xs font-bold text-white/20 mb-4 tracking-widest">STEP {item.step}</div>
              <div className="text-3xl mb-4">{item.icon}</div>
              <h3 className="font-bold text-white mb-2">{item.title}</h3>
              <p className="text-sm text-white/50 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-6 max-w-6xl mx-auto w-full">
        <div className="text-center mb-16">
          <p className="section-label mb-3">Features</p>
          <h2 className="text-3xl md:text-4xl font-bold">
            Research-grade <span className="text-gradient">adaptive learning</span>
          </h2>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[
            {
              icon: "🎯",
              title: "RAG-Grounded Questions",
              desc: "Every question is verified against your uploaded material using cosine similarity. Hallucinations are detected and rejected.",
              badge: "Research Metric",
              badgeType: "badge-violet",
            },
            {
              icon: "📈",
              title: "Real-time Difficulty Adaptation",
              desc: "Correct answer → harder question. Wrong answer → easier with hint. Implements Item Response Theory principles.",
              badge: "IRT Model",
              badgeType: "badge-cyan",
            },
            {
              icon: "🌿",
              title: "Bloom's Taxonomy Mapping",
              desc: "Questions span Remember → Analyze. The system tracks your coverage across all cognitive levels.",
              badge: "6 Levels",
              badgeType: "badge-green",
            },
            {
              icon: "🤖",
              title: "Multi-Agent LangGraph",
              desc: "7 specialized agents: Ingestion, Knowledge, Quiz, Evaluation, Adaptive, Recommendation, Analytics.",
              badge: "7 Agents",
              badgeType: "badge-violet",
            },
            {
              icon: "⚡",
              title: "Qwen2.5-7B on Modal.com",
              desc: "Open-source LLM runs serverlessly on GPU. No OpenAI dependency — fully reproducible for research.",
              badge: "Open Source",
              badgeType: "badge-cyan",
            },
            {
              icon: "📋",
              title: "MCQ + Structured + Essay",
              desc: "Choose your exam format. All types support adaptive difficulty and grounding verification.",
              badge: "3 Types",
              badgeType: "badge-green",
            },
          ].map((f) => (
            <div key={f.title} className="glass-card-hover p-6">
              <div className="text-3xl mb-4">{f.icon}</div>
              <div className="flex items-start justify-between gap-2 mb-3">
                <h3 className="font-bold text-white text-lg leading-tight">{f.title}</h3>
                <span className={`${f.badgeType} shrink-0 mt-0.5`}>{f.badge}</span>
              </div>
              <p className="text-sm text-white/50 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Banner */}
      <section className="py-20 px-6 max-w-4xl mx-auto w-full text-center">
        <div className="glass-card p-12" style={{ background: "linear-gradient(135deg, rgba(124,58,237,0.15) 0%, rgba(79,70,229,0.1) 100%)" }}>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready to test your knowledge?
          </h2>
          <p className="text-white/60 mb-8 text-lg">Upload your study material and start your first adaptive quiz in minutes.</p>
          <Link href="/upload" id="cta-banner-start" className="btn-primary text-base px-10 py-4">
            Get Started Free →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 text-center text-white/30 text-sm border-t border-white/5">
        AdaptiveIQ — MSc Research Project · Adaptive AI Assessment Platform · Built with LangGraph + Qwen2.5 + Next.js
      </footer>
    </main>
  );
}
