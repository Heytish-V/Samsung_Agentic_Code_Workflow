import { useState, useRef, useCallback } from "react";
import Editor from "@monaco-editor/react";
import WhyThisResult from "./components/WhyThisResult";

const API = "http://127.0.0.1:8000";

function App() {
  const [query, setQuery] = useState(
    "Where is user authentication token validated and refreshed?"
  );
  const [results, setResults] = useState([]);
  const [trace, setTrace] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("READY");

  // Structural query state
  const [mode, setMode] = useState("search"); // "search" | "structural"
  const [funcBefore, setFuncBefore] = useState("sanitize_input");
  const [funcAfter, setFuncAfter] = useState("validate_signature");
  const [structuralResults, setStructuralResults] = useState(null);

  // Graph visualization state
  const [graphData, setGraphData] = useState(null);

  // Monaco editor ref for line highlighting
  const editorRef = useRef(null);
  const decorationsRef = useRef([]);

  const runSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setStatus("SEARCHING");
    setStructuralResults(null);

    try {
      const response = await fetch(`${API}/api/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query,
          top_k: 5,
          enable_agent: true,
        }),
      });

      if (!response.ok) {
        throw new Error("API request failed");
      }

      const data = await response.json();

      setResults(data.results || []);
      setTrace(data.agent_trace || []);
      setSelected(data.results?.[0] || null);
      setStatus("COMPLETE");

      // Fetch graph for top result
      if (data.results?.[0]?.chunk_id) {
        fetchGraph(data.results[0].chunk_id);
      }
    } catch (error) {
      console.error(error);
      setStatus("API ERROR");
    } finally {
      setLoading(false);
    }
  };

  const runStructuralQuery = async () => {
    if (!funcBefore.trim() || !funcAfter.trim()) return;

    setLoading(true);
    setStatus("STRUCTURAL QUERY");
    setResults([]);
    setTrace([]);

    try {
      const response = await fetch(`${API}/api/structural-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          func_before: funcBefore,
          func_after: funcAfter,
        }),
      });

      if (!response.ok) throw new Error("Structural query failed");

      const data = await response.json();
      setStructuralResults(data);
      setStatus("COMPLETE");
    } catch (error) {
      console.error(error);
      setStatus("API ERROR");
    } finally {
      setLoading(false);
    }
  };

  const fetchGraph = async (chunkId) => {
    try {
      const response = await fetch(
        `${API}/api/graph/subgraph?chunk_id=${encodeURIComponent(chunkId)}&depth=2`
      );
      if (response.ok) {
        const data = await response.json();
        setGraphData(data);
      }
    } catch (e) {
      // Graph viz is optional
    }
  };

  const handleEditorDidMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
  }, []);

  // Apply line decorations when selected result changes
  const applyDecorations = useCallback((editor, monaco) => {
    if (!editor || !selected) return;

    const decorations = [];

    // Highlight the full code range
    if (selected.start_line && selected.end_line) {
      decorations.push({
        range: new monaco.Range(1, 1, 1, 1),
        options: {
          isWholeLine: true,
          className: "monaco-first-line",
          glyphMarginClassName: "monaco-glyph-start",
        },
      });
    }

    // Highlight matched call sites from evidence
    if (selected.evidence) {
      for (const ev of selected.evidence) {
        if (ev.factor === "structural" && selected.why_matched) {
          // Parse line numbers from structural evidence
          const lineMatch = selected.why_matched.match(/line (\d+)/g);
          if (lineMatch) {
            for (const lm of lineMatch) {
              const lineNum = parseInt(lm.replace("line ", ""), 10);
              const relLine = lineNum - (selected.start_line - 1);
              if (relLine > 0) {
                decorations.push({
                  range: new monaco.Range(relLine, 1, relLine, 1),
                  options: {
                    isWholeLine: true,
                    className: "monaco-call-highlight",
                    glyphMarginClassName: "monaco-call-glyph",
                  },
                });
              }
            }
          }
        }
      }
    }

    decorationsRef.current = editor.deltaDecorations(
      decorationsRef.current,
      decorations
    );
  }, [selected]);

  return (
    <div className="app">
      <style>{`
        * {
          box-sizing: border-box;
        }

        body {
          margin: 0;
          background: #0b0d10;
          color: #f1f5f9;
          font-family: Inter, ui-sans-serif, system-ui, -apple-system,
            BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        button,
        input,
        textarea {
          font: inherit;
        }

        .app {
          min-height: 100vh;
          background:
            radial-gradient(
              circle at 20% 0%,
              rgba(77, 163, 255, 0.08),
              transparent 30%
            ),
            radial-gradient(
              circle at 90% 10%,
              rgba(139, 156, 255, 0.06),
              transparent 28%
            ),
            #0b0d10;
        }

        .topbar {
          height: 68px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 28px;
          border-bottom: 1px solid #252c34;
          background: rgba(11, 13, 16, 0.92);
        }

        .brand {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .brand-icon {
          width: 38px;
          height: 38px;
          border: 1px solid #4da3ff;
          border-radius: 9px;
          display: grid;
          place-items: center;
          color: #4da3ff;
          font-weight: 800;
          background: rgba(77, 163, 255, 0.08);
        }

        .brand-title {
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 0.2px;
        }

        .brand-subtitle {
          color: #8994a3;
          font-size: 11px;
          margin-top: 2px;
        }

        .system-status {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #8994a3;
          font-size: 11px;
          letter-spacing: 0.8px;
        }

        .status-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #4ade80;
          box-shadow: 0 0 10px rgba(74, 222, 128, 0.45);
        }

        .workspace {
          display: grid;
          grid-template-columns:
            290px
            minmax(340px, 1fr)
            minmax(420px, 1.25fr);
          min-height: calc(100vh - 68px);
        }

        .panel {
          min-width: 0;
          border-right: 1px solid #252c34;
          background: rgba(17, 21, 26, 0.72);
        }

        .panel:last-child {
          border-right: none;
        }

        .panel-header {
          padding: 18px 20px 14px;
          border-bottom: 1px solid #252c34;
        }

        .panel-title {
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 1.2px;
          text-transform: uppercase;
        }

        .panel-description {
          margin-top: 5px;
          color: #697585;
          font-size: 11px;
        }

        .panel-content {
          padding: 18px;
        }

        .label {
          display: block;
          margin-bottom: 8px;
          color: #8994a3;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 1px;
          text-transform: uppercase;
        }

        textarea, .input-field {
          width: 100%;
          padding: 13px;
          border: 1px solid #2a333d;
          border-radius: 9px;
          outline: none;
          background: #0e1216;
          color: #e7edf5;
          line-height: 1.5;
          font-size: 12px;
        }

        textarea {
          min-height: 112px;
          resize: vertical;
        }

        textarea:focus, .input-field:focus {
          border-color: #4da3ff;
          box-shadow: 0 0 0 2px rgba(77, 163, 255, 0.08);
        }

        .mode-tabs {
          display: flex;
          gap: 4px;
          margin-bottom: 16px;
        }

        .mode-tab {
          flex: 1;
          padding: 8px 6px;
          border: 1px solid #2a333d;
          border-radius: 7px;
          background: #0e1216;
          color: #8994a3;
          cursor: pointer;
          font-size: 10px;
          font-weight: 700;
          text-align: center;
          letter-spacing: 0.5px;
          transition: all 0.15s ease;
        }

        .mode-tab:hover {
          border-color: #4da3ff;
        }

        .mode-tab.active {
          background: #173554;
          border-color: #4da3ff;
          color: #eaf4ff;
        }

        .search-button {
          width: 100%;
          margin-top: 12px;
          padding: 11px 14px;
          border: 1px solid #4da3ff;
          border-radius: 8px;
          background: #173554;
          color: #eaf4ff;
          cursor: pointer;
          font-size: 12px;
          font-weight: 700;
          transition: background 0.15s ease;
        }

        .search-button:hover {
          background: #1d446b;
        }

        .search-button:disabled {
          opacity: 0.55;
          cursor: not-allowed;
        }

        .divider {
          height: 1px;
          background: #252c34;
          margin: 22px 0;
        }

        .control-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 0;
          border-bottom: 1px solid #1d242c;
          font-size: 11px;
        }

        .control-value {
          color: #4da3ff;
        }

        .trace-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .trace-item {
          display: flex;
          gap: 11px;
          padding: 11px;
          border: 1px solid #252c34;
          border-radius: 8px;
          background: #11161b;
        }

        .trace-number {
          min-width: 23px;
          height: 23px;
          border-radius: 6px;
          display: grid;
          place-items: center;
          background: #182b40;
          color: #4da3ff;
          font-size: 10px;
          font-weight: 800;
        }

        .trace-tool {
          color: #dbe7f5;
          font-size: 11px;
          font-weight: 700;
        }

        .trace-result {
          margin-top: 4px;
          color: #7f8b99;
          font-size: 10px;
          line-height: 1.45;
        }

        /* WHY THIS RESULT */

        .why-card {
          margin-top: 18px;
          padding: 15px;
          border: 1px solid #314252;
          border-radius: 9px;
          background:
            linear-gradient(
              145deg,
              rgba(77, 163, 255, 0.08),
              rgba(17, 21, 26, 0.9)
            );
        }

        .why-title {
          color: #4da3ff;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 0.8px;
          text-transform: uppercase;
          margin-bottom: 12px;
        }

        .why-scores {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 7px;
        }

        .why-score {
          padding: 8px;
          border: 1px solid #27333f;
          border-radius: 6px;
          background: rgba(10, 14, 18, 0.65);
        }

        .why-score span {
          display: block;
          color: #697585;
          font-size: 9px;
          text-transform: uppercase;
          letter-spacing: 0.6px;
        }

        .why-score strong {
          display: block;
          margin-top: 4px;
          color: #dbeafe;
          font-size: 11px;
        }

        .why-reason {
          margin-top: 11px;
          padding-top: 10px;
          border-top: 1px solid #27333f;
          color: #aab5c3;
          font-size: 10px;
          line-height: 1.55;
        }

        .result-list {
          display: flex;
          flex-direction: column;
          gap: 9px;
        }

        .result-card {
          padding: 13px;
          border: 1px solid #252c34;
          border-radius: 8px;
          background: #11161b;
          cursor: pointer;
          transition: border-color 0.15s ease;
        }

        .result-card:hover,
        .result-card.selected {
          border-color: #4da3ff;
        }

        .result-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
        }

        .rank {
          color: #4da3ff;
          font-size: 10px;
          font-weight: 800;
        }

        .score {
          color: #72d6a0;
          font-size: 11px;
          font-weight: 800;
        }

        .file-name {
          margin-top: 7px;
          color: #e2e8f0;
          font-family: "Cascadia Code", "Consolas", monospace;
          font-size: 11px;
        }

        .symbol {
          margin-top: 4px;
          color: #7f8b99;
          font-size: 10px;
        }

        .confidence-badge {
          display: inline-block;
          padding: 2px 7px;
          border-radius: 4px;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: 0.5px;
        }

        .confidence-HIGH {
          background: rgba(74, 222, 128, 0.15);
          color: #4ade80;
          border: 1px solid rgba(74, 222, 128, 0.3);
        }

        .confidence-MEDIUM {
          background: rgba(250, 204, 21, 0.12);
          color: #facc15;
          border: 1px solid rgba(250, 204, 21, 0.3);
        }

        .confidence-LOW {
          background: rgba(248, 113, 113, 0.12);
          color: #f87171;
          border: 1px solid rgba(248, 113, 113, 0.3);
        }

        .code-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 17px;
          border-bottom: 1px solid #252c34;
          background: #0f1317;
        }

        .code-file {
          color: #cbd5e1;
          font-family: "Cascadia Code", "Consolas", monospace;
          font-size: 11px;
        }

        .line-info {
          color: #697585;
          font-size: 10px;
        }

        .code-view {
          min-height: 300px;
          overflow: hidden;
          background: #090c0f;
        }

        .score-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
          padding: 14px;
          border-top: 1px solid #252c34;
        }

        .score-box {
          padding: 9px;
          border: 1px solid #252c34;
          border-radius: 7px;
          background: #11161b;
        }

        .score-label {
          color: #697585;
          font-size: 9px;
          text-transform: uppercase;
        }

        .score-number {
          margin-top: 4px;
          color: #dce8f5;
          font-size: 12px;
          font-weight: 700;
        }

        .empty {
          color: #697585;
          font-size: 11px;
          line-height: 1.5;
          padding: 18px 0;
        }

        /* Structural Results */
        .structural-card {
          padding: 14px;
          border: 1px solid #314252;
          border-radius: 9px;
          background: linear-gradient(145deg, rgba(74, 222, 128, 0.05), rgba(17, 21, 26, 0.9));
          margin-bottom: 10px;
        }

        .structural-tier {
          display: inline-block;
          padding: 3px 8px;
          border-radius: 4px;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: 0.5px;
          margin-bottom: 8px;
        }

        .tier-1 {
          background: rgba(74, 222, 128, 0.15);
          color: #4ade80;
          border: 1px solid rgba(74, 222, 128, 0.3);
        }

        .tier-2 {
          background: rgba(250, 204, 21, 0.12);
          color: #facc15;
          border: 1px solid rgba(250, 204, 21, 0.3);
        }

        .structural-evidence {
          color: #aab5c3;
          font-size: 11px;
          line-height: 1.5;
          margin-top: 6px;
        }

        .structural-caller {
          color: #e2e8f0;
          font-family: "Cascadia Code", "Consolas", monospace;
          font-size: 11px;
          margin-top: 4px;
        }

        /* Call Graph Visualization */
        .graph-panel {
          padding: 14px;
          border-top: 1px solid #252c34;
        }

        .graph-title {
          color: #8994a3;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 1px;
          text-transform: uppercase;
          margin-bottom: 10px;
        }

        .graph-container {
          position: relative;
          width: 100%;
          height: 200px;
          border: 1px solid #252c34;
          border-radius: 8px;
          background: #090c0f;
          overflow: hidden;
        }

        .graph-node {
          position: absolute;
          padding: 4px 8px;
          border-radius: 5px;
          font-size: 9px;
          font-weight: 700;
          white-space: nowrap;
          cursor: pointer;
          transition: all 0.15s ease;
          z-index: 2;
        }

        .graph-node:hover {
          transform: scale(1.1);
        }

        .graph-node.center {
          background: #173554;
          color: #4da3ff;
          border: 1px solid #4da3ff;
        }

        .graph-node.caller {
          background: rgba(74, 222, 128, 0.12);
          color: #4ade80;
          border: 1px solid rgba(74, 222, 128, 0.3);
        }

        .graph-node.callee {
          background: rgba(251, 146, 60, 0.12);
          color: #fb923c;
          border: 1px solid rgba(251, 146, 60, 0.3);
        }

        .graph-node.external {
          background: rgba(148, 163, 184, 0.08);
          color: #94a3b8;
          border: 1px solid rgba(148, 163, 184, 0.2);
        }

        .graph-legend {
          display: flex;
          gap: 12px;
          margin-top: 8px;
          font-size: 9px;
          color: #697585;
        }

        .graph-legend-item {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .graph-legend-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }

        /* Monaco decorations */
        .monaco-call-highlight {
          background: rgba(74, 222, 128, 0.12) !important;
          border-left: 3px solid #4ade80 !important;
        }

        .monaco-call-glyph {
          background: #4ade80;
          border-radius: 50%;
          margin-left: 3px;
        }

        .monaco-first-line {
          background: rgba(77, 163, 255, 0.06) !important;
        }

        /* Input field for structural query */
        .struct-input-row {
          display: flex;
          gap: 8px;
          margin-bottom: 10px;
        }

        .struct-input-row .input-field {
          flex: 1;
        }

        .struct-arrow {
          display: flex;
          align-items: center;
          color: #4da3ff;
          font-size: 14px;
          font-weight: 800;
        }

        @media (max-width: 1000px) {
          .workspace {
            grid-template-columns: 1fr;
          }

          .panel {
            border-right: none;
            border-bottom: 1px solid #252c34;
          }
        }
      `}</style>

      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">&lt;/&gt;</div>

          <div>
            <div className="brand-title">
              Samsung PRISM · Agentic Code Intelligence
            </div>

            <div className="brand-subtitle">
              Hybrid Retrieval + Structural Reasoning + Call Graph
            </div>
          </div>
        </div>

        <div className="system-status">
          <span className="status-dot"></span>
          SYSTEM {status}
        </div>
      </header>

      <main className="workspace">

        {/* LEFT PANEL */}
        <section className="panel">
          <div className="panel-header">
            <div className="panel-title">
              Search & Controls
            </div>

            <div className="panel-description">
              Query the indexed codebase
            </div>
          </div>

          <div className="panel-content">
            {/* Mode Tabs */}
            <div className="mode-tabs">
              <div
                className={`mode-tab ${mode === "search" ? "active" : ""}`}
                onClick={() => setMode("search")}
              >
                HYBRID SEARCH
              </div>
              <div
                className={`mode-tab ${mode === "structural" ? "active" : ""}`}
                onClick={() => setMode("structural")}
              >
                AST STRUCTURAL
              </div>
            </div>

            {mode === "search" ? (
              <>
                <label className="label">
                  Natural Language Query
                </label>

                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask something about the codebase..."
                />

                <button
                  className="search-button"
                  onClick={runSearch}
                  disabled={loading}
                >
                  {loading
                    ? "RUNNING AGENT..."
                    : "RUN AGENT SEARCH"}
                </button>
              </>
            ) : (
              <>
                <label className="label">
                  Statement Ordering Query
                </label>

                <div style={{ color: "#8994a3", fontSize: "10px", marginBottom: "12px" }}>
                  Find functions that call X strictly before Y
                </div>

                <div className="struct-input-row">
                  <input
                    className="input-field"
                    value={funcBefore}
                    onChange={(e) => setFuncBefore(e.target.value)}
                    placeholder="func_before"
                  />
                  <div className="struct-arrow">→</div>
                  <input
                    className="input-field"
                    value={funcAfter}
                    onChange={(e) => setFuncAfter(e.target.value)}
                    placeholder="func_after"
                  />
                </div>

                <button
                  className="search-button"
                  onClick={runStructuralQuery}
                  disabled={loading}
                >
                  {loading
                    ? "QUERYING AST..."
                    : "RUN STRUCTURAL QUERY"}
                </button>
              </>
            )}

            <div className="divider"></div>

            <div className="control-row">
              <span>Top K</span>
              <span className="control-value">5</span>
            </div>

            <div className="control-row">
              <span>Semantic Search</span>
              <span className="control-value">ON</span>
            </div>

            <div className="control-row">
              <span>BM25 Search</span>
              <span className="control-value">ON</span>
            </div>

            <div className="control-row">
              <span>Graph Expansion</span>
              <span className="control-value">ON</span>
            </div>

            <div className="control-row">
              <span>Query Classification</span>
              <span className="control-value">ON</span>
            </div>
          </div>
        </section>

        {/* CENTER PANEL */}
        <section className="panel">
          <div className="panel-header">
            <div className="panel-title">
              Agent Trace
            </div>

            <div className="panel-description">
              Reasoning and retrieval execution
            </div>
          </div>

          <div className="panel-content">

            {/* Structural Results */}
            {structuralResults && (
              <div style={{ marginBottom: "18px" }}>
                <div className="label">
                  {structuralResults.predicate}
                </div>
                {structuralResults.matches.length === 0 ? (
                  <div className="empty">
                    No AST-verified matches found.
                  </div>
                ) : (
                  structuralResults.matches.map((match, idx) => (
                    <div className="structural-card" key={idx}>
                      <div className={`structural-tier ${match.confidence >= 1.0 ? "tier-1" : "tier-2"}`}>
                        {match.confidence >= 1.0
                          ? "TIER 1: AST-VERIFIED (100%)"
                          : "TIER 2: GRAPH REACHABILITY (75%)"}
                      </div>
                      <div className="structural-caller">
                        {match.caller}
                      </div>
                      <div className="structural-evidence">
                        {match.evidence}
                      </div>
                      <div style={{ color: "#697585", fontSize: "10px", marginTop: "4px" }}>
                        {match.file} · L{match.start_line}–L{match.end_line}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Agent Trace */}
            {trace.length === 0 && !structuralResults ? (
              <div className="empty">
                Run an agent search to see the retrieval trace.
              </div>
            ) : (
              <div className="trace-list">
                {trace.map((step) => (
                  <div
                    className="trace-item"
                    key={step.step}
                  >
                    <div className="trace-number">
                      {step.step}
                    </div>

                    <div>
                      <div className="trace-tool">
                        {step.tool}
                      </div>

                      {step.target && (
                        <div className="trace-result">
                          {step.target}
                        </div>
                      )}

                      <div className="trace-result">
                        {step.result}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* NEW WHY THIS RESULT COMPONENT */}
            <WhyThisResult result={selected} />

          </div>
        </section>

        {/* RIGHT PANEL */}
        <section className="panel">

          <div className="panel-header">
            <div className="panel-title">
              Retrieved Candidates
            </div>

            <div className="panel-description">
              Ranked results and source code
            </div>
          </div>

          <div className="panel-content">

            {results.length === 0 ? (
              <div className="empty">
                Search results will appear here.
              </div>
            ) : (
              <div className="result-list">

                {results.map((result) => (
                  <div
                    key={result.chunk_id}
                    className={`result-card ${
                      selected?.chunk_id === result.chunk_id
                        ? "selected"
                        : ""
                    }`}
                    onClick={() => {
                      setSelected(result);
                      if (result.chunk_id) fetchGraph(result.chunk_id);
                    }}
                  >

                    <div className="result-top">

                      <span className="rank">
                        #{result.rank}
                      </span>

                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        {result.confidence_level && (
                          <span className={`confidence-badge confidence-${result.confidence_level}`}>
                            {result.confidence_level}
                          </span>
                        )}
                        <span className="score">
                          {result.final_score.toFixed(3)}
                        </span>
                      </div>

                    </div>

                    <div className="file-name">
                      {result.file}
                    </div>

                    <div className="symbol">
                      {result.symbol} · lines{" "}
                      {result.start_line}-
                      {result.end_line}
                    </div>

                  </div>
                ))}

              </div>
            )}

          </div>

          {selected && (
            <>
              <div className="code-header">

                <span className="code-file">
                  {selected.file}::{selected.symbol}
                </span>

                <span className="line-info">
                  L{selected.start_line}–
                  L{selected.end_line}
                </span>

              </div>

              <div className="code-view">

                <Editor
                  height="300px"
                  language="python"
                  theme="vs-dark"
                  value={selected.code}
                  onMount={(editor, monaco) => {
                    handleEditorDidMount(editor, monaco);
                    applyDecorations(editor, monaco);
                  }}
                  options={{
                    readOnly: true,
                    minimap: {
                      enabled: false,
                    },
                    fontSize: 13,
                    lineNumbers: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    glyphMargin: true,
                    padding: {
                      top: 12,
                    },
                  }}
                />

              </div>

              <div className="score-grid">

                <div className="score-box">
                  <div className="score-label">
                    Semantic
                  </div>

                  <div className="score-number">
                    {selected.score_breakdown.semantic}
                  </div>
                </div>

                <div className="score-box">
                  <div className="score-label">
                    BM25
                  </div>

                  <div className="score-number">
                    {selected.score_breakdown.bm25}
                  </div>
                </div>

                <div className="score-box">
                  <div className="score-label">
                    Symbol
                  </div>

                  <div className="score-number">
                    {selected.score_breakdown.symbol}
                  </div>
                </div>

                <div className="score-box">
                  <div className="score-label">
                    Graph
                  </div>

                  <div className="score-number">
                    {selected.score_breakdown.graph}
                  </div>
                </div>

              </div>
            </>
          )}

          {/* Call Graph Visualization */}
          {graphData && graphData.nodes && graphData.nodes.length > 0 && (
            <div className="graph-panel">
              <div className="graph-title">Call Graph Neighborhood</div>
              <div className="graph-container">
                {(() => {
                  const center = graphData.center_id;
                  const nodes = graphData.nodes || [];
                  const edges = graphData.edges || [];

                  // Simple layout: center node in middle, others in a circle
                  const centerX = 50;
                  const centerY = 50;
                  const radius = 35;

                  const callers = new Set();
                  const callees = new Set();
                  edges.forEach(e => {
                    if (e.target === center) callers.add(e.source);
                    if (e.source === center) callees.add(e.target);
                  });

                  const otherNodes = nodes.filter(n => n.id !== center);
                  const angleStep = otherNodes.length > 0 ? (2 * Math.PI) / otherNodes.length : 0;

                  return (
                    <>
                      {/* Center node */}
                      <div
                        className="graph-node center"
                        style={{
                          left: `${centerX}%`,
                          top: `${centerY}%`,
                          transform: "translate(-50%, -50%)",
                        }}
                        title={center}
                      >
                        {center.split("::").pop()}
                      </div>

                      {/* Other nodes */}
                      {otherNodes.map((node, idx) => {
                        const angle = angleStep * idx - Math.PI / 2;
                        const x = centerX + radius * Math.cos(angle);
                        const y = centerY + radius * Math.sin(angle);
                        const nodeClass = node.is_external
                          ? "external"
                          : callers.has(node.id)
                            ? "caller"
                            : callees.has(node.id)
                              ? "callee"
                              : "callee";

                        return (
                          <div
                            key={node.id}
                            className={`graph-node ${nodeClass}`}
                            style={{
                              left: `${x}%`,
                              top: `${y}%`,
                              transform: "translate(-50%, -50%)",
                            }}
                            title={node.id}
                            onClick={() => {
                              // Find this node in results and select it
                              const match = results.find(r => r.chunk_id === node.id);
                              if (match) setSelected(match);
                            }}
                          >
                            {node.symbol}
                          </div>
                        );
                      })}

                      {/* SVG lines for edges */}
                      <svg
                        style={{
                          position: "absolute",
                          top: 0,
                          left: 0,
                          width: "100%",
                          height: "100%",
                          pointerEvents: "none",
                          zIndex: 1,
                        }}
                      >
                        {otherNodes.map((node, idx) => {
                          const angle = angleStep * idx - Math.PI / 2;
                          const x = centerX + radius * Math.cos(angle);
                          const y = centerY + radius * Math.sin(angle);
                          const isCaller = callers.has(node.id);
                          const isCallee = callees.has(node.id);

                          if (!isCaller && !isCallee) return null;

                          return (
                            <line
                              key={node.id}
                              x1={`${centerX}%`}
                              y1={`${centerY}%`}
                              x2={`${x}%`}
                              y2={`${y}%`}
                              stroke={isCaller ? "#4ade80" : "#fb923c"}
                              strokeWidth="1"
                              strokeOpacity="0.4"
                            />
                          );
                        })}
                      </svg>
                    </>
                  );
                })()}
              </div>

              <div className="graph-legend">
                <div className="graph-legend-item">
                  <div className="graph-legend-dot" style={{ background: "#4da3ff" }}></div>
                  Selected
                </div>
                <div className="graph-legend-item">
                  <div className="graph-legend-dot" style={{ background: "#4ade80" }}></div>
                  Callers
                </div>
                <div className="graph-legend-item">
                  <div className="graph-legend-dot" style={{ background: "#fb923c" }}></div>
                  Callees
                </div>
                <div className="graph-legend-item">
                  <div className="graph-legend-dot" style={{ background: "#94a3b8" }}></div>
                  External
                </div>
              </div>
            </div>
          )}

        </section>

      </main>
    </div>
  );
}

export default App;