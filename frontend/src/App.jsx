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

const ACCEPTED = ["image/png", "image/jpeg", "image/webp"];

export default function App() {
  const [mode, setMode] = useState("single");
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  function update(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function takeFile(f) {
    if (!f) return;
    if (!ACCEPTED.includes(f.type)) {
      setError("Please choose a PNG, JPEG, or WebP image of the label.");
      return;
    }
    setError(null);
    setResult(null);
    setFile(f);
    setPreviewUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(f);
    });
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!file) {
      setError("Please add a photo of the label first.");
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
      const res = await verifyLabel(file, {
        ...form,
        is_import: form.is_import ? "true" : "false",
      });
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
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
        Add a photo of the label, enter what the application says, then press
        Verify label.
      </p>

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
            takeFile(e.dataTransfer.files[0]);
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
          aria-label="Add a photo of the label"
        >
          {previewUrl ? (
            <img src={previewUrl} alt="The label photo you added" className="preview" />
          ) : (
            <p>
              <strong>Click here to add the label photo</strong>
              <br />
              or drag and drop it into this box
            </p>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED.join(",")}
            hidden
            onChange={(e) => takeFile(e.target.files[0])}
          />
        </div>

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

      <div aria-live="polite">
        {error && (
          <div className="error" role="alert">
            <strong>We hit a problem:</strong> {error}
          </div>
        )}
        {result && <ResultView result={result} />}
      </div>
        </>
      )}
    </main>
  );
}
