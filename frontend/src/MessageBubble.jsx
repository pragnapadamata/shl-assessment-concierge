import React from "react";
import RecommendationCard from "./RecomendationCard";

function renderInline(text) {
  return String(text || "").split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    /^\*\*[^*]+\*\*$/.test(p)
      ? <strong key={i} style={{ fontWeight: 600, color: "#0f172a" }}>{p.slice(2, -2)}</strong>
      : <React.Fragment key={i}>{p}</React.Fragment>
  );
}

export default function MessageBubble({ msg }) {
  if (msg.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 18 }}>
        <div style={{
          maxWidth: "78%", background: "var(--shl-primary)", color: "white",
          padding: "12px 16px", borderRadius: "16px 16px 4px 16px",
          fontSize: 14, lineHeight: 1.6, wordBreak: "break-word", whiteSpace: "pre-wrap"
        }}>
          {msg.content}
        </div>
      </div>
    );
  }

  const lines = String(msg.content || "").split(/\n+/).filter(Boolean);
  const hasRecs = Array.isArray(msg.recommendations) && msg.recommendations.length > 0;

  return (
    <div style={{ marginBottom: 18 }}>
      {/* Text bubble */}
      <div style={{
        display: "inline-block", maxWidth: "86%",
        background: "#f5f5f4", border: "1px solid #e7e5e4",
        padding: "12px 16px", borderRadius: "16px 16px 16px 4px",
        marginBottom: hasRecs ? 10 : 0
      }}>
        {lines.map((l, i) => (
          <p key={i} style={{ margin: i < lines.length - 1 ? "0 0 6px" : 0, fontSize: 14, lineHeight: 1.65, color: "#1e293b" }}>
            {renderInline(l)}
          </p>
        ))}
      </div>

      {/* Recommendation cards — grid, never clips */}
      {hasRecs && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: 10,
          maxWidth: "92%"
        }}>
          {msg.recommendations.map((r, i) => (
            <RecommendationCard key={`${i}-${r.name}`} rec={r} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
