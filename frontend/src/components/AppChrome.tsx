import { deviceNoun } from "../lib/deviceName";
import type { WorkspaceTab } from "./appTabs";

export function NavIcon({ id }: { id: WorkspaceTab }) {
  const p = {
    className: "nav-icon",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  switch (id) {
    case "overview":
      return (
        <svg {...p}>
          <path d="M3 11.5 12 4l9 7.5" />
          <path d="M5 10v9h14v-9" />
        </svg>
      );
    case "intelligence":
      return (
        <svg {...p}>
          <circle cx="6" cy="6" r="2.4" />
          <circle cx="18" cy="9" r="2.4" />
          <circle cx="7" cy="18" r="2.4" />
          <path d="M8.2 6.7 15.6 8.4M7.2 15.7l9-5M6.4 8.3 6.7 15.6" />
        </svg>
      );
    case "ask":
      return (
        <svg {...p}>
          <path d="M21 11.5a8 8 0 0 1-11.6 7.1L4 20l1.4-5.3A8 8 0 1 1 21 11.5Z" />
        </svg>
      );
    case "models":
      return (
        <svg {...p}>
          <rect x="6.5" y="6.5" width="11" height="11" rx="2" />
          <path d="M9.5 2v3M14.5 2v3M9.5 19v3M14.5 19v3M2 9.5h3M2 14.5h3M19 9.5h3M19 14.5h3" />
        </svg>
      );
    case "settings":
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="3.2" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1" />
        </svg>
      );
    default:
      return null;
  }
}

export function FirstRunWelcome({
  productName,
  onOpen,
  logoSrc,
}: {
  productName: string;
  onOpen: () => void;
  logoSrc: string;
}) {
  return (
    <div className="first-run">
      <div className="first-run-inner">
        <img
          className="first-run-mark"
          src={logoSrc}
          alt={productName}
          width={84}
          height={84}
        />
        <p className="first-run-eyebrow">Local-first</p>
        <h1 className="first-run-title">A quiet place to think with your own projects</h1>
        <p className="first-run-sub">
          Point {productName} at a folder on this {deviceNoun()} and ask anything. Your files,
          your answers — nothing leaves this computer.
        </p>
        <button className="first-run-cta" type="button" onClick={onOpen}>
          Open a project folder
        </button>
        <div className="first-run-foot">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="5" y="11" width="14" height="9" rx="2" />
            <path d="M8 11V8a4 4 0 0 1 8 0v3" />
          </svg>
          Runs entirely offline · no cloud · no accounts
        </div>
      </div>
    </div>
  );
}
