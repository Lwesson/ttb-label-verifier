const VERDICT_META = {
  pass: { icon: "✓", word: "PASS", className: "verdict-pass" },
  review: { icon: "⚠", word: "REVIEW", className: "verdict-review" },
  fail: { icon: "✕", word: "FAIL", className: "verdict-fail" },
  unreadable: { icon: "?", word: "UNREADABLE", className: "verdict-unreadable" },
};

const FIELD_LABELS = {
  brand_name: "Brand name",
  class_type: "Class and type",
  alcohol_content: "Alcohol content",
  net_contents: "Net contents",
  name_address: "Name and address",
  country_of_origin: "Country of origin",
  sulfite_declaration: "Sulfite declaration",
};

const MATCH_WORDS = {
  match: "Match",
  review: "Check this",
  mismatch: "Does not match",
  missing: "Missing",
  not_applicable: "Not checked",
};

const CHECK_WORDS = {
  pass: "Pass",
  fail: "Fail",
  review: "Check this",
  unknown: "Could not assess",
};

export default function ResultView({ result }) {
  const meta = VERDICT_META[result.verdict] || VERDICT_META.unreadable;
  const printedAt = new Date().toLocaleString();
  return (
    <section className={`result ${meta.className}`}>
      <div className="print-header">
        <strong>TTB Label Verification Result</strong>
        <span className="print-date">{printedAt}</span>
      </div>
      <h2>
        <span className="verdict-icon" aria-hidden="true">
          {meta.icon}
        </span>{" "}
        {meta.word}: {result.headline}
      </h2>
      {result.elapsed_seconds != null && (
        <p className="elapsed">Checked in {result.elapsed_seconds} seconds</p>
      )}

      <button type="button" className="print-btn no-print" onClick={() => window.print()}>
        Print or save as PDF
      </button>

      <ul className="reasons">
        {result.reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      <div className="result-tables">
        {result.field_matches.length > 0 && (
          <div>
            <h3>Field by field</h3>
            <table>
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Result</th>
                  <th scope="col">Details</th>
                </tr>
              </thead>
              <tbody>
                {result.field_matches.map((m) => (
                  <tr key={m.field} className={`status-${m.status}`}>
                    <th scope="row">{FIELD_LABELS[m.field] || m.field}</th>
                    <td>{MATCH_WORDS[m.status] || m.status}</td>
                    <td>{m.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {result.warning.checks.length > 0 && (
          <div>
            <h3>Government warning checks</h3>
            <table>
              <thead>
                <tr>
                  <th scope="col">Check</th>
                  <th scope="col">Result</th>
                  <th scope="col">Details</th>
                </tr>
              </thead>
              <tbody>
                {result.warning.checks.map((c) => (
                  <tr key={c.name} className={`status-${c.status}`}>
                    <th scope="row">{c.name}</th>
                    <td>{CHECK_WORDS[c.status] || c.status}</td>
                    <td>{c.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
