export default function WhyThisResult({ result }) {
  if (!result) return null;

  const sb = result.score_breakdown || {};
  const evidence = result.evidence || [];
  const confidence = result.confidence_level || "MEDIUM";

  const confidenceColors = {
    HIGH: { bg: "rgba(74, 222, 128, 0.08)", border: "rgba(74, 222, 128, 0.3)", text: "#4ade80" },
    MEDIUM: { bg: "rgba(250, 204, 21, 0.08)", border: "rgba(250, 204, 21, 0.3)", text: "#facc15" },
    LOW: { bg: "rgba(248, 113, 113, 0.08)", border: "rgba(248, 113, 113, 0.3)", text: "#f87171" },
  };

  const cc = confidenceColors[confidence] || confidenceColors.MEDIUM;

  return (
    <div className="why-card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <div className="why-title">Why This Result</div>
        <span
          style={{
            padding: "3px 10px",
            borderRadius: "5px",
            fontSize: "9px",
            fontWeight: 800,
            letterSpacing: "0.6px",
            background: cc.bg,
            border: `1px solid ${cc.border}`,
            color: cc.text,
          }}
        >
          {confidence} CONFIDENCE
        </span>
      </div>

      <div className="why-scores">
        <div className="why-score">
          <span>Semantic</span>
          <strong>{(sb.semantic ?? 0).toFixed(2)}</strong>
        </div>

        <div className="why-score">
          <span>BM25</span>
          <strong>{(sb.bm25 ?? 0).toFixed(2)}</strong>
        </div>

        <div className="why-score">
          <span>Symbol</span>
          <strong>{(sb.symbol ?? 0).toFixed(2)}</strong>
        </div>

        <div className="why-score">
          <span>Graph</span>
          <strong>{(sb.graph ?? 0).toFixed(2)}</strong>
        </div>
      </div>

      {/* Structured evidence */}
      {evidence.length > 0 && (
        <div style={{ marginTop: "14px" }}>
          <div style={{
            color: "#697585",
            fontSize: "9px",
            fontWeight: 700,
            letterSpacing: "0.8px",
            textTransform: "uppercase",
            marginBottom: "8px",
          }}>
            Evidence Chain
          </div>

          {evidence.map((ev, idx) => (
            <div
              key={idx}
              style={{
                padding: "7px 10px",
                marginBottom: "5px",
                borderRadius: "5px",
                border: "1px solid #1d242c",
                background: "rgba(10, 14, 18, 0.5)",
                fontSize: "10px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <span style={{
                  color: "#4da3ff",
                  fontWeight: 700,
                  marginRight: "8px",
                  textTransform: "uppercase",
                  fontSize: "9px",
                }}>
                  {ev.factor}
                </span>
                <span style={{ color: "#aab5c3" }}>
                  {ev.description}
                </span>
              </div>
              <span style={{
                color: ev.score >= 0.7 ? "#4ade80" : ev.score >= 0.4 ? "#facc15" : "#f87171",
                fontWeight: 700,
                fontSize: "11px",
              }}>
                {ev.score.toFixed(3)}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="why-reason">
        {result.why_matched || "Score breakdown shown above."}
      </div>
    </div>
  );
}