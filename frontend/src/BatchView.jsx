import { useRef, useState } from "react";

const VERDICT_META = {
  pass: { icon: "✓", word: "PASS", className: "chip-pass" },
  review: { icon: "⚠", word: "REVIEW", className: "chip-review" },
  fail: { icon: "✕", word: "FAIL", className: "chip-fail" },
  unreadable: { icon: "?", word: "UNREADABLE", className: "chip-unreadable" },
  error: { icon: "!", word: "ERROR", className: "chip-error" },
};

const SAMPLE_MANIFEST =
  "filename,beverage_type,brand_name,class_type,abv_percent,net_contents,name_address,country_of_origin,is_import\n" +
  'clean_bourbon.png,distilled_spirits,RIDGE & RYE,Kentucky Straight Bourbon Whiskey,45,750 mL,"Bottled by Ridge & Rye Distilling Co., Bardstown, KY",,\n' +
  "table_wine.png,wine,MEADOWLARK CELLARS,Red Table Wine,12,750 mL,,,\n" +
  "glen_morrig.png,distilled_spirits,GLEN MORRIG,Single Malt Scotch Whisky,43,750 mL,,Scotland,true\n";

function downloadSample() {
  const blob = new Blob([SAMPLE_MANIFEST], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sample_manifest.csv";
  a.click();
  URL.revokeObjectURL(url);
}

function itemVerdict(item) {
  return item.error ? "error" : item.result.verdict;
}

function needsAttention(item) {
  return itemVerdict(item) !== "pass";
}

export default function BatchView() {
  const [manifestFile, setManifestFile] = useState(null);
  const [imageFiles, setImageFiles] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [elapsed, setElapsed] = useState(null);
  const [onlyProblems, setOnlyProblems] = useState(true);
  const manifestRef = useRef(null);
  const imagesRef = useRef(null);

  async function run() {
    if (!manifestFile) {
      setError("Please choose the manifest CSV first. Use the sample manifest to see the format.");
      return;
    }
    if (imageFiles.length === 0) {
      setError("Please choose the label images (you can select many at once).");
      return;
    }
    setRunning(true);
    setError(null);
    setItems([]);
    setSummary(null);
    setElapsed(null);
    setTotal(0);
    try {
      const form = new FormData();
      form.append("manifest", manifestFile);
      for (const f of imageFiles) form.append("images", f);
      const res = await fetch("/api/verify-batch", { method: "POST", body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body && body.detail ? body.detail : "Something went wrong. Please try again.");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (!line) continue;
          const msg = JSON.parse(line);
          if (msg.type === "start") setTotal(msg.total);
          else if (msg.type === "result") setItems((old) => [...old, msg]);
          else if (msg.type === "done") {
            setSummary(msg.summary);
            setElapsed(msg.elapsed_seconds);
          }
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  const problems = items.filter(needsAttention);
  const shown = onlyProblems ? problems : items;

  return (
    <section>
      <p className="lede">
        Upload a manifest CSV (what each application says) plus the label images,
        then run the whole batch at once.{" "}
        <button type="button" className="linklike" onClick={downloadSample}>
          Download a sample manifest
        </button>
      </p>

      <div className="batch-pickers">
        <div>
          <label htmlFor="manifest">Manifest CSV</label>
          <input
            id="manifest"
            ref={manifestRef}
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setManifestFile(e.target.files[0] || null)}
          />
        </div>
        <div>
          <label htmlFor="images">Label images (select many)</label>
          <input
            id="images"
            ref={imagesRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple
            onChange={(e) => setImageFiles([...e.target.files])}
          />
        </div>
      </div>

      <button type="button" className="primary" onClick={run} disabled={running}>
        {running ? "Checking labels..." : "Run batch"}
      </button>

      {error && (
        <div className="error" role="alert">
          <strong>We hit a problem:</strong> {error}
        </div>
      )}

      <div aria-live="polite">
        {(running || items.length > 0) && total > 0 && (
          <p className="progress-text">
            Checked {items.length} of {total}
            <progress value={items.length} max={total} />
          </p>
        )}

        {summary && (
          <p className="summary-chips">
            {Object.entries(summary).map(([k, v]) =>
              v > 0 ? (
                <span key={k} className={`chip ${VERDICT_META[k].className}`}>
                  <span aria-hidden="true">{VERDICT_META[k].icon}</span> {v} {VERDICT_META[k].word}
                </span>
              ) : null
            )}
            {elapsed != null && <span className="chip">done in {elapsed}s</span>}
          </p>
        )}

        {items.length > 0 && (
          <div className="filter-row">
            <input
              id="only-problems"
              type="checkbox"
              checked={onlyProblems}
              onChange={(e) => setOnlyProblems(e.target.checked)}
            />
            <label htmlFor="only-problems">Show only labels that need attention</label>
          </div>
        )}

        {summary && onlyProblems && problems.length === 0 && (
          <p className="all-clear">All {items.length} labels look good.</p>
        )}

        <ul className="batch-list">
          {shown.map((item, i) => {
            const v = itemVerdict(item);
            const meta = VERDICT_META[v];
            return (
              <li key={`${item.filename}-${i}`}>
                <details>
                  <summary>
                    <span className={`chip ${meta.className}`}>
                      <span aria-hidden="true">{meta.icon}</span> {meta.word}
                    </span>{" "}
                    <strong>{item.filename}</strong>{" "}
                    {item.error
                      ? item.error
                      : item.result.reasons[0] || item.result.headline}
                  </summary>
                  {item.error ? (
                    <p>{item.error}</p>
                  ) : (
                    <>
                      <p>
                        {item.result.headline}
                        {item.result.elapsed_seconds != null &&
                          ` (checked in ${item.result.elapsed_seconds}s)`}
                      </p>
                      <ul>
                        {item.result.reasons.map((r, j) => (
                          <li key={j}>{r}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </details>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
