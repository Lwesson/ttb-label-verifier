import { useRef, useState } from "react";
import { verifyLabel } from "./api.js";
import BatchView from "./BatchView.jsx";
import ResultView from "./ResultView.jsx";

const BEVERAGE_TYPES = [
  { value: "distilled_spirits", label: "Distilled spirits (whiskey, vodka, gin...)" },
  { value: "wine", label: "Wine" },
  { value: "malt", label: "Malt beverage (beer, ale...)" },
];

const EMPTY_FORM = {
  beverage_type: "distilled_spirits",
  brand_name: "",
  class_type: "",
  abv_percent: "",
  net_contents: "",
  name_address: "",
  country_of_origin: "",
  is_import: false,
};

// One-click demo labels (bundled in public/samples) so a first-time visitor can
// see a result without hunting for a bottle photo. Same application values; one
// label matches (PASS), the other has a title-case warning (FAIL).
const SAMPLE_VALUES = {
  beverage_type: "distilled_spirits",
  brand_name: "RIDGE & RYE",
  class_type: "Kentucky Straight Bourbon Whiskey",
  abv_percent: "45",
  net_contents: "750 mL",
  name_address: "Bottled by Ridge & Rye Distilling Co., Bardstown, KY",
};

const SAMPLES = {
  pass: {
    image: "/samples/clean_bourbon.png",
    filename: "clean_bourbon.png",
    values: SAMPLE_VALUES,
  },
  problem: {
    image: "/samples/warning_title_case.png",
    filename: "warning_title_case.png",
    values: SAMPLE_VALUES,
  },
};

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];
const ACCEPT_ATTR =
  "image/png,image/jpeg,image/webp,image/heic,image/heif,application/pdf,.heic,.heif";
const ACCEPTED_EXT = [".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".pdf"];
const MAX_IMAGES = 5;

function isAccepted(f) {
  // HEIC often arrives with an empty or wrong MIME type, so fall back to the
  // file extension.
  if (IMAGE_TYPES.includes(f.type)) return true;
  if (["image/heic", "image/heif", "application/pdf"].includes(f.type)) return true;
  const name = (f.name || "").toLowerCase();
  return ACCEPTED_EXT.some((ext) => name.endsWith(ext));
}

function isPreviewable(f) {
  return IMAGE_TYPES.includes(f.type);
}

let _uid = 0;

export default function App() {
  const [mode, setMode] = useState("single");
  const [form, setForm] = useState(EMPTY_FORM);
  const [items, setItems] = useState([]); // { id, file, url }
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  function update(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function takeFiles(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) return;
    setError(null);
    setResult(null);
    setItems((prev) => {
      const next = [...prev];
      for (const f of files) {
        if (next.length >= MAX_IMAGES) {
          setError(`You can add up to ${MAX_IMAGES} photos of one label.`);
          break;
        }
        if (!isAccepted(f)) {
          setError("Please choose PNG, JPEG, WebP, HEIC, or PDF files of the label.");
          continue;
        }
        next.push({
          id: ++_uid,
          file: f,
          url: isPreviewable(f) ? URL.createObjectURL(f) : null,
        });
      }
      return next;
    });
  }

  function removeItem(id) {
    setItems((prev) => {
      const found = prev.find((it) => it.id === id);
      if (found && found.url) URL.revokeObjectURL(found.url);
      return prev.filter((it) => it.id !== id);
    });
    setResult(null);
  }

  async function loadSample(sample) {
    setError(null);
    setResult(null);
    try {
      const res = await fetch(sample.image);
      if (!res.ok) throw new Error("could not fetch sample");
      const blob = await res.blob();
      const file = new File([blob], sample.filename, { type: blob.type || "image/png" });
      setItems((prev) => {
        prev.forEach((it) => it.url && URL.revokeObjectURL(it.url));
        return [{ id: ++_uid, file, url: URL.createObjectURL(file) }];
      });
      setForm({ ...EMPTY_FORM, ...sample.values });
    } catch {
      setError("Could not load the sample. Please upload a photo of the label instead.");
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (items.length === 0) {
      setError("Please add at least one photo of the label first.");
      return;
    }
    if (!form.brand_name.trim()) {
      setError("Please enter the brand name from the application.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await verifyLabel(
        items.map((it) => it.file),
        { ...form, is_import: form.is_import ? "true" : "false" },
      );
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={mode === "single" ? "page single-view" : "page"}>
      <h1>TTB Label Verifier</h1>

      <div className="tabs" role="tablist" aria-label="Verification mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "single"}
          className={mode === "single" ? "tab active" : "tab"}
          onClick={() => setMode("single")}
        >
          One label
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "batch"}
          className={mode === "batch" ? "tab active" : "tab"}
          onClick={() => setMode("batch")}
        >
          Batch
        </button>
      </div>

      {mode === "batch" ? (
        <BatchView />
      ) : (
        <>
        <p className="lede">
          Add one or more photos of the label (front, back, a close-up of the small
          print), enter what the application says, then press Verify label.
        </p>
        <div className="single-grid">
          <div className="pane form-card">
            <form onSubmit={onSubmit} noValidate>
              <div
                className={dragOver ? "dropzone dragover" : "dropzone"}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  takeFiles(e.dataTransfer.files);
                }}
                onClick={() => inputRef.current.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    inputRef.current.click();
                  }
                }}
                role="button"
                tabIndex={0}
                aria-label="Add photos of the label"
              >
                <p>
                  <strong>Click here to add label photos</strong>
                  <br />
                  or drag and drop them here (front, back, close-ups)
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPT_ATTR}
                  multiple
                  hidden
                  onChange={(e) => {
                    takeFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
              </div>

              <p className="sample-hint">
                No label handy? Try{" "}
                <button type="button" className="linklike" onClick={() => loadSample(SAMPLES.pass)}>
                  a passing bourbon
                </button>
                {" or "}
                <button type="button" className="linklike" onClick={() => loadSample(SAMPLES.problem)}>
                  one with a title-case warning
                </button>
                .
              </p>

              {items.length > 0 && (
                <ul className="thumbs">
                  {items.map((it) => (
                    <li key={it.id} className="thumb">
                      {it.url ? (
                        <img src={it.url} alt={`Label photo: ${it.file.name}`} />
                      ) : (
                        <span className="thumb-file">{it.file.name}</span>
                      )}
                      <button
                        type="button"
                        className="thumb-remove"
                        aria-label={`Remove ${it.file.name}`}
                        onClick={() => removeItem(it.id)}
                      >
                        &times;
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <fieldset>
                <legend>What does the application say?</legend>

                <label htmlFor="beverage_type">Beverage type</label>
                <select
                  id="beverage_type"
                  value={form.beverage_type}
                  onChange={(e) => update("beverage_type", e.target.value)}
                >
                  {BEVERAGE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>

                <label htmlFor="brand_name">Brand name (required)</label>
                <input
                  id="brand_name"
                  type="text"
                  value={form.brand_name}
                  onChange={(e) => update("brand_name", e.target.value)}
                  placeholder="Example: Stone's Throw"
                />

                <label htmlFor="class_type">Class and type</label>
                <input
                  id="class_type"
                  type="text"
                  value={form.class_type}
                  onChange={(e) => update("class_type", e.target.value)}
                  placeholder="Example: Kentucky Straight Bourbon Whiskey"
                />

                <div className="row">
                  <div>
                    <label htmlFor="abv_percent">Alcohol content (% ABV)</label>
                    <input
                      id="abv_percent"
                      type="number"
                      inputMode="decimal"
                      step="0.1"
                      min="0"
                      max="99"
                      value={form.abv_percent}
                      onChange={(e) => update("abv_percent", e.target.value)}
                      placeholder="Example: 45"
                    />
                  </div>
                  <div>
                    <label htmlFor="net_contents">Net contents</label>
                    <input
                      id="net_contents"
                      type="text"
                      value={form.net_contents}
                      onChange={(e) => update("net_contents", e.target.value)}
                      placeholder="Example: 750 mL"
                    />
                  </div>
                </div>

                <label htmlFor="name_address">Bottler name and address (optional)</label>
                <input
                  id="name_address"
                  type="text"
                  value={form.name_address}
                  onChange={(e) => update("name_address", e.target.value)}
                  placeholder="Example: Bottled by Ridge & Rye Distilling Co., Bardstown, KY"
                />

                <div className="import-row">
                  <input
                    id="is_import"
                    type="checkbox"
                    checked={form.is_import}
                    onChange={(e) => update("is_import", e.target.checked)}
                  />
                  <label htmlFor="is_import">This product is imported</label>
                </div>

                {form.is_import && (
                  <>
                    <label htmlFor="country_of_origin">Country of origin</label>
                    <input
                      id="country_of_origin"
                      type="text"
                      value={form.country_of_origin}
                      onChange={(e) => update("country_of_origin", e.target.value)}
                      placeholder="Example: Scotland"
                    />
                  </>
                )}
              </fieldset>

              <button type="submit" className="primary" disabled={loading}>
                {loading ? "Checking the label..." : "Verify label"}
              </button>
            </form>
          </div>

          <div className="pane result-col" aria-live="polite">
            {error ? (
              <div className="error" role="alert">
                <strong>We hit a problem:</strong> {error}
              </div>
            ) : result ? (
              <ResultView result={result} />
            ) : (
              <div className="result-placeholder">
                <p className="placeholder-lead">
                  Your result shows up here. Every label gets one of these:
                </p>
                <ul className="verdict-legend">
                  <li className="verdict-pass"><b>&#10003; PASS</b> Looks good</li>
                  <li className="verdict-review"><b>&#9888; REVIEW</b> A person should take a look</li>
                  <li className="verdict-fail"><b>&#10007; FAIL</b> Problem found</li>
                  <li className="verdict-unreadable"><b>? UNREADABLE</b> Photo too unclear, add a clearer one</li>
                </ul>
              </div>
            )}
          </div>
        </div>
        </>
      )}
    </main>
  );
}
