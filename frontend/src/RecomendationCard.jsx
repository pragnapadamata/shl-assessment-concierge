import React from "react";
import { ExternalLink, Clock, Globe, Briefcase } from "lucide-react";

const TYPE_LABEL = { K: "Knowledge", P: "Personality", A: "Ability", S: "Simulation", J: "Judgment" };
const TYPE_COLOR = { K: "#1d4ed8", P: "#7c3aed", A: "#0369a1", S: "#b45309", J: "#15803d" };

export default function RecommendationCard({ rec, index }) {
  const name = rec?.name || "Untitled";
  const url  = rec?.url  || "#";
  const type = rec?.test_type || "K";

  return (
    <a
      href={url} target="_blank" rel="noopener noreferrer"
      className="shl-rise"
      style={{
        display: "flex", flexDirection: "column", gap: 10,
        background: "white", border: "1px solid #e2e8f0",
        borderRadius: 12, padding: "14px 16px",
        textDecoration: "none", color: "inherit",
        transition: "box-shadow 0.2s, transform 0.2s",
        animationDelay: `${index * 0.05}s`
      }}
      onMouseEnter={e => { e.currentTarget.style.boxShadow = "0 6px 20px rgba(0,0,0,0.1)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.transform = "none"; }}
    >
      {/* Name + icon */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <span style={{ fontFamily: "var(--shl-font-heading)", fontWeight: 700, fontSize: 14, color: "#0f172a", lineHeight: 1.35 }}>
          {name}
        </span>
        <ExternalLink size={13} style={{ color: "#94a3b8", flexShrink: 0, marginTop: 2 }} />
      </div>

      {/* Type badge */}
      <span style={{
        display: "inline-block", width: "fit-content",
        fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em",
        color: TYPE_COLOR[type] || "#334155",
        background: (TYPE_COLOR[type] || "#334155") + "18",
        padding: "2px 7px", borderRadius: 4
      }}>
        {TYPE_LABEL[type] || "Assessment"}
      </span>

      {/* Meta chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
        {rec?.duration && rec.duration !== "n/a" && (
          <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11, color: "#475569", background: "#f1f5f9", padding: "2px 7px", borderRadius: 20 }}>
            <Clock size={10} />{rec.duration}
          </span>
        )}
        {rec?.remote === "yes" && (
          <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11, color: "#475569", background: "#f1f5f9", padding: "2px 7px", borderRadius: 20 }}>
            <Globe size={10} />Remote
          </span>
        )}
        {Array.isArray(rec?.job_levels) && rec.job_levels.length > 0 && (
          <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11, color: "#475569", background: "#f1f5f9", padding: "2px 7px", borderRadius: 20 }}>
            <Briefcase size={10} />{rec.job_levels.slice(0, 2).join(", ")}{rec.job_levels.length > 2 ? ` +${rec.job_levels.length - 2}` : ""}
          </span>
        )}
      </div>

      {/* CTA */}
      <div style={{
        marginTop: "auto", textAlign: "center", fontSize: 12, fontWeight: 600,
        color: "var(--shl-accent)", padding: "6px 0",
        border: "1px solid var(--shl-accent)", borderRadius: 7,
        transition: "background 0.15s, color 0.15s"
      }}
        onMouseEnter={e => { e.currentTarget.style.background = "var(--shl-accent)"; e.currentTarget.style.color = "white"; }}
        onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--shl-accent)"; }}
      >
        View on SHL catalog
      </div>
    </a>
  );
}
