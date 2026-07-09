import { Link } from "react-router-dom";

export default function BracketSandboxPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <Link
        to="/"
        className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors mb-8 inline-block"
      >
        ← 返回首页
      </Link>

      <header className="mb-8">
        <h1 className="text-3xl font-bold mb-2">🏟️ Bracket Sandbox</h1>
        <p className="text-[var(--color-text-muted)]">
          交互式淘汰赛推演沙盘 · 切换情景 · 实时重算 · AI Pundit 分析
        </p>
      </header>

      {/* Placeholder — Phase 4 will build the full SVG + Framer Motion sandbox */}
      <div className="bg-[var(--color-surface)] rounded-xl p-12 text-center min-h-[400px] flex flex-col items-center justify-center">
        <p className="text-6xl mb-4">🏗️</p>
        <p className="text-xl text-[var(--color-text-muted)]">
          Bracket Sandbox 将在 Phase 4 构建
        </p>
        <p className="text-sm text-[var(--color-text-muted)] mt-2">
          SVG 对阵树 · Framer Motion 动画 · 情景切换 · AI Pundit 实时推理
        </p>
      </div>
    </div>
  );
}
