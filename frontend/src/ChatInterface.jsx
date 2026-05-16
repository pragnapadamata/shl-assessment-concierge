import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Send, Sparkles, RefreshCcw, AlertCircle, Wrench } from "lucide-react";
import MessageBubble from "./MessageBubble";

// Use env var if set (production), otherwise localhost
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "https://shl-assessment-concierge.onrender.com";
const API = `${BACKEND_URL}/api`;
const MAX_TURNS = 8;

const SUGGESTIONS = [
  "We need assessments for senior leadership selection — CXO level.",
  "Screening 500 entry-level contact centre agents, inbound calls.",
  "Senior Rust engineer, high-performance networking infrastructure.",
  "Graduate financial analysts — numerical reasoning + finance knowledge.",
];

export default function ChatInterface() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [ended, setEnded] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);
  const taRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, error]);

  const turnsUsed = messages.length;
  const atCap = turnsUsed >= MAX_TURNS;

  async function sendMessage(text) {
    const clean = (text ?? input).trim();
    if (!clean || loading || ended || atCap) return;
    setError(null);
    const next = [...messages, { role: "user", content: clean }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/chat`, {
        messages: next.map((m) => ({ role: m.role, content: m.content })),
      }, { timeout: 30000 });
      setMessages([...next, {
        role: "assistant",
        content: data.reply || "",
        recommendations: data.recommendations || [],
      }]);
      if (data.end_of_conversation) setEnded(true);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Something went wrong.");
    } finally {
      setLoading(false);
      setTimeout(() => taRef.current?.focus(), 50);
    }
  }

  function reset() {
    setMessages([]); setEnded(false); setError(null); setInput("");
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  return (
    <div className="shl-page-bg" style={{ height: "100dvh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        maxWidth: 900, width: "100%", margin: "0 auto",
        display: "flex", flexDirection: "column",
        height: "100%", overflow: "hidden",
        borderLeft: "1px solid #e5e5e0", borderRight: "1px solid #e5e5e0",
        background: "rgba(255,255,255,0.65)"
      }}>

        {/* HEADER — fixed height, never shrinks */}
        <header style={{
          flexShrink: 0,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 24px",
          background: "rgba(255,255,255,0.95)", backdropFilter: "blur(12px)",
          borderBottom: "1px solid #e5e5e0", zIndex: 10
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: "var(--shl-primary)", color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontWeight: 900, fontSize: 12, letterSpacing: "-0.02em", flexShrink: 0
            }}>SHL</div>
            <div>
              <div style={{ fontFamily: "var(--shl-font-heading)", fontWeight: 800, fontSize: 17, color: "#0f172a", letterSpacing: "-0.02em" }}>
                Assessment Concierge
              </div>
              <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.14em", color: "#78716c", fontWeight: 600 }}>
                AI · catalog-grounded
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#78716c" }}>
              <Wrench size={12} />{turnsUsed}/{MAX_TURNS}
            </span>
            <button onClick={reset} style={{
              display: "flex", alignItems: "center", gap: 5,
              fontSize: 12, fontWeight: 600, color: "#334155",
              padding: "6px 12px", borderRadius: 8,
              border: "1px solid #e2e8f0", background: "white", cursor: "pointer"
            }}>
              <RefreshCcw size={12} /> New chat
            </button>
          </div>
        </header>

        {/* MESSAGES — flex-1 + overflow-y-auto = scrolls, never clips */}
        <main className="shl-scroll" style={{
          flex: 1, overflowY: "auto", overflowX: "hidden",
          padding: "28px 28px 16px"
        }}>
          {messages.length === 0
            ? <EmptyState onPick={sendMessage} />
            : messages.map((m, i) => <MessageBubble key={i} msg={m} index={i} />)
          }

          {loading && (
            <div style={{ display: "flex", marginTop: 16 }}>
              <div style={{
                background: "#f5f5f4", border: "1px solid #e7e5e4",
                borderRadius: "16px 16px 16px 4px",
                padding: "12px 16px", display: "flex", alignItems: "center", gap: 5
              }}>
                <span className="shl-typing-dot" />
                <span className="shl-typing-dot" />
                <span className="shl-typing-dot" />
              </div>
            </div>
          )}

          {error && (
            <div style={{
              display: "flex", alignItems: "flex-start", gap: 8,
              maxWidth: "88%", background: "#fff1f2",
              border: "1px solid #fecdd3", color: "#9f1239",
              padding: "12px 14px", borderRadius: 10, fontSize: 13, marginTop: 16
            }}>
              <AlertCircle size={14} style={{ marginTop: 1, flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {(ended || atCap) && messages.length > 0 && (
            <div style={{ textAlign: "center", fontSize: 12, color: "#78716c", padding: "16px 0" }}>
              {atCap ? "Reached the 8-turn cap." : "Conversation complete."}{" "}
              <button onClick={reset} style={{ textDecoration: "underline", background: "none", border: "none", cursor: "pointer", color: "inherit" }}>
                Start a new chat
              </button>
            </div>
          )}

          {/* Scroll anchor — always at the very bottom */}
          <div ref={bottomRef} />
        </main>

        {/* INPUT — flexShrink:0 so it's always visible, never overlaps messages */}
        <div style={{
          flexShrink: 0,
          borderTop: "1px solid #e5e5e0",
          background: "white",
          padding: "14px 24px 12px"
        }}>
          <div style={{
            position: "relative", display: "flex", alignItems: "flex-end",
            background: "white", border: "1px solid #cbd5e1",
            borderRadius: 14, boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
            overflow: "hidden"
          }}>
            <textarea
              ref={taRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={ended || atCap
                ? "Conversation closed — start a new one."
                : "Describe the role, skills, or constraints…"}
              disabled={loading || ended || atCap}
              rows={1}
              style={{
                flex: 1, minHeight: 50, maxHeight: 120,
                resize: "none", background: "transparent",
                border: "none", outline: "none",
                padding: "13px 52px 13px 14px",
                fontSize: 14, fontFamily: "var(--shl-font-body)",
                color: "#0f172a", lineHeight: 1.5,
                opacity: loading || ended || atCap ? 0.5 : 1
              }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={loading || !input.trim() || ended || atCap}
              style={{
                position: "absolute", right: 8, bottom: 7,
                width: 34, height: 34, borderRadius: 9,
                background: "var(--shl-primary)", border: "none",
                color: "white", display: "flex", alignItems: "center",
                justifyContent: "center", cursor: "pointer",
                opacity: loading || !input.trim() || ended || atCap ? 0.35 : 1,
                transition: "opacity 0.15s"
              }}
              aria-label="Send"
            >
              <Send size={14} />
            </button>
          </div>
          <p style={{ textAlign: "center", fontSize: 11, color: "#a8a29e", marginTop: 6, marginBottom: 0 }}>
            Stateless · full history each turn · 8-turn cap · catalog-grounded
          </p>
        </div>

      </div>
    </div>
  );
}

function EmptyState({ onPick }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      textAlign: "center", padding: "24px 8px 0", maxWidth: 580, margin: "0 auto"
    }}>
      <div style={{
        width: 52, height: 52, borderRadius: 14, background: "#f5f5f4",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "var(--shl-accent)", marginBottom: 18
      }}>
        <Sparkles size={24} />
      </div>
      <h1 style={{
        fontFamily: "var(--shl-font-heading)", fontSize: 26, fontWeight: 800,
        color: "#0f172a", letterSpacing: "-0.02em", marginBottom: 10, lineHeight: 1.25
      }}>
        From vague intent to a grounded shortlist.
      </h1>
      <p style={{ fontSize: 14, color: "#78716c", marginBottom: 24, maxWidth: 400, lineHeight: 1.65 }}>
        Describe who you're hiring and what you want to measure — I'll suggest SHL Individual Test Solutions from the official catalog.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, width: "100%" }}>
        {SUGGESTIONS.map((s, i) => (
          <button key={i} onClick={() => onPick(s)} style={{
            textAlign: "left", padding: "11px 14px", borderRadius: 10,
            border: "1px solid #e2e8f0", background: "white",
            fontSize: 13, fontWeight: 500, color: "#334155",
            cursor: "pointer", lineHeight: 1.5, transition: "border-color 0.15s"
          }}
            onMouseEnter={e => e.currentTarget.style.borderColor = "#0f172a"}
            onMouseLeave={e => e.currentTarget.style.borderColor = "#e2e8f0"}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
