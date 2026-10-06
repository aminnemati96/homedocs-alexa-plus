export type ToolRun = {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output?: unknown;
  isError?: boolean;
  ms?: number;
};

/** Shows each MCP tool call live, so viewers can see what the assistant looked up. */
export default function ToolPanel({ runs, thinking }: { runs: ToolRun[]; thinking: boolean }) {
  return (
    <aside className="tools">
      <h2>Under the hood</h2>
      <p className="tools-sub">
        Bedrock model &rarr; <code>homedocs</code> MCP server (Streamable HTTP)
      </p>

      {runs.length === 0 && (
        <p className="tools-empty">{thinking ? "Waiting for the model..." : "Tool calls will appear here."}</p>
      )}

      <ol className="tool-list">
        {runs.map((run) => (
          <li key={run.id} className={`tool ${run.output === undefined ? "pending" : run.isError ? "failed" : "done"}`}>
            <div className="tool-head">
              <code className="tool-name">{run.name}</code>
              <span className="tool-time">
                {run.output === undefined ? "running" : run.isError ? "error" : `${run.ms} ms`}
              </span>
            </div>
            <pre className="tool-io">{JSON.stringify(run.input)}</pre>
            {run.output !== undefined && (
              <details>
                <summary>Result</summary>
                <pre className="tool-io">{JSON.stringify(run.output, null, 2)}</pre>
              </details>
            )}
          </li>
        ))}
      </ol>
    </aside>
  );
}
