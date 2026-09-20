import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { ShieldCheck, User, Lock, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { PageTransition } from "@/components/page-transition";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [{ title: "Sign in — Aegis Credit" }],
  }),
  component: LoginPage,
});

// ─── Decorative motifs ──────────────────────────────────────────────────────
// Everything below is presentational-only ambient texture for the login
// background/right-panel — aria-hidden, pointer-events-none, and never
// sourced from or claiming to be real application data. Illustrative values
// (98.2%, 0.937, "43 models", etc.) match the approved reference composition
// but are static brand texture, not live metrics.

function Sparkline({ points, color }: { points: string; color: string }) {
  return (
    <svg width="52" height="26" viewBox="0 0 52 26" fill="none" aria-hidden>
      <path d={`M${points} L52,26 L0,26 Z`} fill={color} fillOpacity="0.12" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MiniBars({ color }: { color: string }) {
  const bars = [0.5, 0.75, 0.6, 0.9, 0.7, 0.85, 1];
  return (
    <svg width="44" height="26" viewBox="0 0 44 26" fill="none" aria-hidden>
      {bars.map((h, i) => (
        <rect
          key={i}
          className="bar-pulse"
          x={i * 6.5}
          y={26 - h * 22}
          width="4.5"
          height={h * 22}
          rx="1"
          fill={color}
          fillOpacity={0.55 + i * 0.05}
          style={{ transformOrigin: "bottom", transformBox: "fill-box", animationDelay: `${-i * 0.6}s` }}
        />
      ))}
    </svg>
  );
}

function MetricMotif({
  label,
  value,
  sub,
  chart,
  accent,
  style,
}: {
  label: string;
  value: string;
  sub?: string;
  chart: React.ReactNode;
  accent: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      aria-hidden
      className="motif-float pointer-events-none absolute hidden select-none xl:block"
      style={style}
    >
      <div className="text-[9px] font-semibold uppercase tracking-widest text-slate-400">{label}</div>
      <div className="mt-0.5 flex items-end gap-1.5">
        <div className="text-lg font-bold leading-none" style={{ color: accent }}>{value}</div>
        {sub ? <div className="mb-0.5 text-[10px] font-medium text-slate-400">{sub}</div> : null}
      </div>
      <div className="mt-1">{chart}</div>
    </div>
  );
}

const WAVE_PATHS = [
  "M -60,560 C 160,480 380,540 600,500 S 880,430 1100,470 S 1320,510 1500,460",
  "M -60,620 C 200,560 400,600 660,570 S 960,520 1200,550 S 1380,580 1500,540",
  "M -60,680 C 240,640 480,660 700,640 S 1000,610 1260,630 S 1420,650 1500,620",
];

const FLOAT_DOTS = [
  { cx: 90, cy: 380, r: 4, c: "#93c5fd", dur: 13, amp: 16, delay: 0 },
  { cx: 260, cy: 460, r: 5, c: "#60a5fa", dur: 17, amp: 20, delay: -3 },
  { cx: 810, cy: 240, r: 4, c: "#93c5fd", dur: 15, amp: 14, delay: -6 },
  { cx: 1080, cy: 310, r: 5, c: "#a5b4fc", dur: 19, amp: 22, delay: -2 },
  { cx: 1300, cy: 430, r: 3.5, c: "#60a5fa", dur: 14, amp: 12, delay: -8 },
  { cx: 640, cy: 680, r: 3, c: "#bae6fd", dur: 16, amp: 18, delay: -5 },
];

function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Enter a username and password to continue.");
      return;
    }
    // Accept any non-empty username and password for demo; do not
    // validate against fixed credentials.

    login(username, password);
    navigate({ to: "/" });
  }

  return (
    <PageTransition intent="login">
      <div
        className="login-anim relative -mx-4 -my-6 flex min-h-[calc(100vh-60px)] flex-col items-center justify-center overflow-hidden px-4 py-10 md:-mx-8 md:-my-8"
        style={{
          background: "linear-gradient(155deg, #f2f6fc 0%, #eaf1fb 40%, #eef4ff 70%, #f6f9ff 100%)",
          backgroundSize: "180% 180%",
        }}
      >
        <style>{`
        .login-anim { animation: bgDrift 46s ease-in-out infinite; }
        .login-anim .orb-a { animation: orbDriftA 27s ease-in-out infinite; }
        .login-anim .orb-b { animation: orbDriftB 33s ease-in-out infinite; }
        .login-anim .wave-0 { animation: waveDrift0 18s ease-in-out infinite; }
        .login-anim .wave-1 { animation: waveDrift1 24s ease-in-out infinite; }
        .login-anim .wave-2 { animation: waveDrift2 30s ease-in-out infinite; }
        .login-anim .dot-float { animation-name: dotFloat; animation-timing-function: ease-in-out; animation-iteration-count: infinite; }
        .ring-breathe-1 { animation: ringBreathe 22s ease-in-out infinite; }
        .ring-breathe-2 { animation: ringBreathe 26s ease-in-out infinite reverse; }
        .motif-float { animation-name: motifFloat; animation-timing-function: ease-in-out; animation-iteration-count: infinite; opacity: 0.32; }
        .bar-pulse { animation: barPulse 5s ease-in-out infinite; }
        .login-card-enter { animation: cardEnter 0.55s cubic-bezier(0.16, 1, 0.3, 1) both; }

        @keyframes bgDrift {
          0%, 100% { background-position: 0% 0%; }
          50% { background-position: 100% 60%; }
        }
        @keyframes orbDriftA {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50% { transform: translate3d(38px, -30px, 0) scale(1.06); }
        }
        @keyframes orbDriftB {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50% { transform: translate3d(-34px, 26px, 0) scale(1.05); }
        }
        @keyframes waveDrift0 {
          0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.4; }
          50% { transform: translate3d(26px, -6px, 0); opacity: 0.68; }
        }
        @keyframes waveDrift1 {
          0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.32; }
          50% { transform: translate3d(-22px, 5px, 0); opacity: 0.58; }
        }
        @keyframes waveDrift2 {
          0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.28; }
          50% { transform: translate3d(18px, 4px, 0); opacity: 0.5; }
        }
        @keyframes dotFloat {
          0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.5; }
          50% { transform: translate3d(0, calc(var(--float-amp, 16px) * -1), 0); opacity: 0.95; }
        }
        @keyframes ringBreathe {
          0%, 100% { transform: scale(1); opacity: 0.35; }
          50% { transform: scale(1.06); opacity: 0.6; }
        }
        @keyframes motifFloat {
          0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.26; }
          50% { transform: translate3d(0, -10px, 0); opacity: 0.4; }
        }
        @keyframes barPulse {
          0%, 100% { transform: scaleY(1); }
          50% { transform: scaleY(1.18); }
        }
        @keyframes cardEnter {
          from { opacity: 0; transform: translateY(14px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        @media (prefers-reduced-motion: reduce) {
          .login-anim, .login-anim .orb-a, .login-anim .orb-b, .login-anim .wave-0, .login-anim .wave-1,
          .login-anim .wave-2, .login-anim .dot-float, .ring-breathe-1, .ring-breathe-2,
          .motif-float, .bar-pulse {
            animation: none !important;
          }
          .login-anim .wave-0, .login-anim .wave-1, .login-anim .wave-2 { opacity: 0.4 !important; }
          .motif-float { opacity: 0.32 !important; }
          .login-card-enter { animation: none !important; }
        }
      `}</style>

      {/* ── Background canvas: orbs, curves, traveling data points, floating
          dots — every moving piece uses transform/opacity (GPU-friendly),
          each with its own duration/delay so nothing is synchronized. ───── */}
      <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden>
        <defs>
          <radialGradient id="loginOrb1" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#bfdbfe" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#bfdbfe" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="loginOrb2" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#c7d2fe" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#c7d2fe" stopOpacity="0" />
          </radialGradient>
          <filter id="loginSoftBlur" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="38" />
          </filter>
        </defs>

        <ellipse className="orb-a" cx="230" cy="360" rx="380" ry="320" fill="url(#loginOrb1)" filter="url(#loginSoftBlur)" style={{ transformBox: "fill-box", transformOrigin: "center" }} />
        <ellipse className="orb-b" cx="1220" cy="520" rx="340" ry="280" fill="url(#loginOrb2)" filter="url(#loginSoftBlur)" style={{ transformBox: "fill-box", transformOrigin: "center" }} />

        {WAVE_PATHS.map((d, i) => (
          <path
            key={i}
            className={`wave-${i}`}
            d={d}
            fill="none"
            stroke={["#93c5fd", "#a5b4fc", "#bae6fd"][i]}
            strokeWidth={1.3 - i * 0.15}
            strokeDasharray={`${6 - i}  ${8 + i}`}
            style={{ transformBox: "fill-box", transformOrigin: "center" }}
          />
        ))}

        {/* Data points that visibly travel along the analytical curves. */}
        {WAVE_PATHS.slice(0, 2).map((d, i) => (
          <circle key={`travel-${i}`} r={i === 0 ? 5 : 4} fill={i === 0 ? "#3b82f6" : "#818cf8"}>
            <animateMotion dur={`${22 + i * 8}s`} repeatCount="indefinite" path={d} rotate="auto" begin={`${-i * 7}s`} />
          </circle>
        ))}

        {FLOAT_DOTS.map((dot, i) => (
          <circle
            key={i}
            className="dot-float"
            cx={dot.cx}
            cy={dot.cy}
            r={dot.r}
            fill={dot.c}
            style={{
              transformBox: "fill-box",
              transformOrigin: "center",
              animationDuration: `${dot.dur}s`,
              animationDelay: `${dot.delay}s`,
              ["--float-amp" as string]: `${dot.amp}px`,
            }}
          />
        ))}

        {/* Bottom-left ambient bar chart — gentle per-bar pulse. */}
        <g transform="translate(50, 700)" opacity="0.2">
          {[18, 28, 22, 36, 30, 42, 38].map((h, i) => (
            <rect key={i} className="bar-pulse" x={i * 14} y={50 - h} width="10" height={h} rx="2" fill="#60a5fa" style={{ transformOrigin: "bottom", transformBox: "fill-box", animationDelay: `${-i * 0.5}s` }} />
          ))}
        </g>
      </svg>

      {/* Ambient decorative KPI motifs — presentational only, hidden below xl */}
      <MetricMotif label="Model Health" value="98.2%" sub="↑ 2.4%" accent="#10b981" chart={<Sparkline points="0,20 10,15 22,17 34,7 44,4 52,2" color="#10b981" />} style={{ top: "16%", left: "6%", animationDuration: "18s", animationDelay: "0s" }} />
      <MetricMotif label="ROC-AUC" value="0.937" accent="#2563eb" chart={<Sparkline points="0,22 10,18 20,20 30,13 40,9 52,5" color="#3b82f6" />} style={{ bottom: "18%", left: "6%", animationDuration: "22s", animationDelay: "-9s" }} />
      <MetricMotif label="Validation Status" value="Active" sub="7/7 checks" accent="#2563eb" chart={<MiniBars color="#3b82f6" />} style={{ top: "16%", right: "6%", animationDuration: "20s", animationDelay: "-5s" }} />
      <MetricMotif label="KS Statistic" value="0.481" accent="#f59e0b" chart={<Sparkline points="0,22 12,18 22,15 32,11 42,13 52,7" color="#f59e0b" />} style={{ bottom: "18%", right: "6%", animationDuration: "16s", animationDelay: "-11s" }} />

      {/* ── Split sign-in card — white form panel + navy welcome panel,
          matching the Figma `landing` reference's two-panel composition. ── */}
      <div
        className="login-card-enter relative z-10 mx-auto flex w-full overflow-hidden rounded-2xl border border-slate-200/80"
        style={{ maxWidth: 680, minHeight: 400, boxShadow: "0 16px 60px rgba(15,23,42,0.14), 0 2px 8px rgba(15,23,42,0.08)" }}
      >
        {/* Left panel — real, unchanged login form. */}
        <div className="flex min-w-0 flex-1 flex-col justify-center bg-white px-6 py-8 sm:px-10 sm:py-10">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl gradient-primary">
              <ShieldCheck className="h-[18px] w-[18px] text-white" />
            </div>
            <div className="leading-tight">
              <div className="text-xs font-semibold tracking-wide text-slate-900">Aegis Credit</div>
              <div className="text-[9px] uppercase tracking-widest text-slate-400">Model Risk Platform</div>
            </div>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Sign in</h1>
          <p className="mb-6 mt-1 text-sm text-slate-400">Use your Aegis account credentials</p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
            <div>
              <label htmlFor="username" className="sr-only">
                Username
              </label>
              <div className="relative">
                <User className="pointer-events-none absolute left-3.5 top-1/2 h-[15px] w-[15px] -translate-y-1/2 text-slate-300 peer-focus:text-blue-600" />
                <input
                  id="username"
                  autoFocus
                  autoComplete="username"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    setError(null);
                  }}
                  placeholder="Username"
                  className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-3.5 text-sm text-slate-900 outline-none transition focus:border-blue-600 focus:bg-white focus:ring-[3px] focus:ring-blue-500/10"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-300" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError(null);
                  }}
                  placeholder="Password"
                  className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-3.5 text-sm text-slate-900 outline-none transition focus:border-blue-600 focus:bg-white focus:ring-[3px] focus:ring-blue-500/10"
                />
              </div>
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <p className="text-xs text-slate-400">Demo mode — enter any username and any password to sign in.</p>

            <button
              type="submit"
              className="mt-1 flex w-full items-center justify-center gap-2 rounded-lg gradient-primary py-2.5 text-sm font-semibold text-white shadow-[0_2px_8px_rgba(37,99,235,0.35)] transition-shadow hover:shadow-[0_4px_14px_rgba(37,99,235,0.45)]"
            >
              Sign in
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>
        </div>

        {/* Right panel — decorative "Welcome Back" side, matching the Figma
            reference exactly (shield mark, heading, supporting copy, two
            static reference pills). Presentational only. */}
        <div
          aria-hidden
          className="relative hidden w-[240px] shrink-0 flex-col items-center justify-center overflow-hidden px-8 py-10 text-center sm:flex"
          style={{ background: "linear-gradient(155deg, #0d1629 0%, #1e3461 55%, #1a3a6e 100%)" }}
        >
          <div
            className="ring-breathe-1 pointer-events-none absolute rounded-full border border-blue-400/10"
            style={{ width: 260, height: 260, top: -60, right: -80 }}
          />
          <div
            className="ring-breathe-2 pointer-events-none absolute rounded-full border border-blue-400/10"
            style={{ width: 190, height: 190, bottom: -40, left: -60 }}
          />

          <div className="relative z-10">
            <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-blue-400/25 bg-blue-500/30">
              <ShieldCheck className="h-[22px] w-[22px] text-white" />
            </div>
            <h2 className="mb-3 text-xl font-bold leading-snug text-slate-50">Welcome Back</h2>
            <p className="mx-auto mb-7 max-w-[170px] text-xs leading-relaxed text-slate-400">
              Sign in to access your model risk and credit analytics workspace
            </p>
            <div className="flex flex-col gap-2">
              {[
                { label: "Model Registry", value: "43 models" },
                { label: "Validation", value: "Active" },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.07] bg-white/5 px-3 py-1.5">
                  <span className="text-[10px] text-slate-500">{item.label}</span>
                  <span className="text-[10px] font-semibold text-blue-400">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <p className="relative z-10 mt-5 text-center text-[10px] font-medium uppercase tracking-widest text-slate-400">
        Aegis Credit · Confidential
      </p>

      <div aria-hidden className="pointer-events-none absolute bottom-6 left-6 z-10 hidden select-none lg:block">
        <p className="text-xs font-bold uppercase leading-relaxed tracking-widest text-slate-300">
          Better Models
          <br />
          Safer Decisions
        </p>
      </div>
      <div aria-hidden className="pointer-events-none absolute bottom-6 right-6 z-10 hidden select-none text-right lg:block">
        <p className="text-[9px] font-medium uppercase leading-loose tracking-widest text-slate-300">
          Powering Responsible
          <br />
          Credit Risk with AI
        </p>
      </div>
      </div>
    </PageTransition>
  );
}
