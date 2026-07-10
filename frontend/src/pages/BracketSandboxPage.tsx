import { Link } from "react-router-dom";
import BracketTree from "../components/BracketTree";

export default function BracketSandboxPage() {
  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8">
      <Link
        to="/"
        className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors mb-8 inline-block"
      >
        ← 返回首页
      </Link>

      <header className="mb-8">
        <h1 className="text-3xl font-bold mb-2">🏟️ Bracket Sandbox</h1>
        <p className="text-[var(--color-text-muted)]">
          交互式淘汰赛推演沙盘 · 五层对阵树 · AI Agent 预测可视化
        </p>
      </header>

      {/* Bracket Tree */}
      <div className="bg-[var(--color-surface)] rounded-xl p-6 overflow-hidden">
        <BracketTree />
      </div>
    </div>
  );
}
