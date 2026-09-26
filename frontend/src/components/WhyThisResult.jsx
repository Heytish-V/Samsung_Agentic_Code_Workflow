function WhyThisResult({ result }) {
  if (!result) {
    return null;
  }

  const { score_breakdown, why_matched } = result;

  return (
    <div className="why-card">
      <div className="why-title">WHY THIS RESULT?</div>

      <div className="why-scores">
        <div className="why-score">
          <span>Semantic</span>
          <strong>{score_breakdown.semantic}</strong>
        </div>

        <div className="why-score">
          <span>BM25</span>
          <strong>{score_breakdown.bm25}</strong>
        </div>

        <div className="why-score">
          <span>Symbol</span>
          <strong>
            {score_breakdown.symbol > 0 ? "✓ PASS" : "NONE"}
          </strong>
        </div>

        <div className="why-score">
          <span>Graph</span>
          <strong>
            {score_breakdown.graph > 0 ? "✓ CONNECTED" : "NONE"}
          </strong>
        </div>
      </div>

      <div className="why-reason">
        {why_matched}
      </div>
    </div>
  );
}

export default WhyThisResult;