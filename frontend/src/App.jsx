import { useState } from "react";
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

  const runSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setStatus("SEARCHING");

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
    } catch (error) {
      console.error(error);
      setStatus("API ERROR");
    } finally {
      setLoading(false);
    }
  };

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

        textarea {
          width: 100%;
          min-height: 112px;
          resize: vertical;
          padding: 13px;
          border: 1px solid #2a333d;
          border-radius: 9px;
          outline: none;
          background: #0e1216;
          color: #e7edf5;
          line-height: 1.5;
          font-size: 12px;
        }

        textarea:focus {
          border-color: #4da3ff;
          box-shadow: 0 0 0 2px rgba(77, 163, 255, 0.08);
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
              Hybrid Retrieval + Structural Reasoning
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

            {trace.length === 0 ? (
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
                    onClick={() => setSelected(result)}
                  >

                    <div className="result-top">

                      <span className="rank">
                        #{result.rank}
                      </span>

                      <span className="score">
                        {result.final_score.toFixed(3)}
                      </span>

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
                  options={{
                    readOnly: true,
                    minimap: {
                      enabled: false,
                    },
                    fontSize: 13,
                    lineNumbers: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
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

        </section>

      </main>
    </div>
  );
}

export default App;