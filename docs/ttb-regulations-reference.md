# TTB Label Requirements: Regulatory Reference

This is the grounded rule set the validation engine is built against. Every rule here is
traceable to the Code of Federal Regulations or TTB guidance so the tool validates against
real requirements, not guesses. Citations at the bottom.

## 1. Government Health Warning Statement

### 1.1 Exact required text (27 CFR 16.21)

The statement must appear word for word:

> **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not drink
> alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption
> of alcoholic beverages impairs your ability to drive a car or operate machinery, and may
> cause health problems.

Canonical string to match against (normalized, single spaces):

```
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

### 1.2 Formatting rules (27 CFR 16.22)

These are the checks that catch labels trying to game the warning:

| Rule | Requirement | How the tool checks it |
|---|---|---|
| Wording | Exact, word for word | Normalized exact string compare |
| Caps | The first two words `GOVERNMENT WARNING` must be in **capital letters** | Case check on the prefix. Catches `Government Warning` title case (a real rejection Jenny described) |
| Bold | Only `GOVERNMENT WARNING` must be **bold**. The remainder must NOT be bold | Best-effort visual assessment (see limitations) |
| Legibility | Readily legible under ordinary conditions, on a **contrasting background** | Best-effort visual assessment |
| Separation | Must appear separate and apart from other information | Best-effort |

### 1.3 Type size by container volume (27 CFR 16.22)

| Container size | Min type size | Max characters per inch |
|---|---|---|
| 237 mL (8 fl oz) or less | 1 mm | 40 |
| More than 237 mL up to 3 L (101 fl oz) | 2 mm | 25 |
| More than 3 L | 3 mm | 12 |

**Honest limitation:** true millimeter compliance cannot be measured from an uploaded photo
without a known physical scale (DPI / container dimensions). The tool measures *relative*
prominence (is the warning conspicuously smaller than the rest of the label) and reports
absolute mm compliance as "requires physical/known-dimension verification." Documenting this
honestly is better than faking a measurement.

## 2. Mandatory Label Information by Beverage Type

The full field set is larger than brand / ABV / warning. Extracting only those three is
incomplete. Requirements vary by commodity (27 CFR parts 4, 5, 7).

### 2.1 Distilled spirits (27 CFR part 5)
- Brand name
- Class and type designation (e.g., "Kentucky Straight Bourbon Whiskey")
- Alcohol content (% alc/vol; proof optional in addition)
- Net contents (standard of fill, metric)
- Name and address of bottler / producer / importer
- Commodity statement
- Government health warning
- Country of origin (imports)

### 2.2 Wine (27 CFR part 4)
- Brand name and class/type on the brand label
- Alcohol content **OR** the table-wine exception (see 2.4)
- Net contents
- Name and address of bottler / importer
- Sulfite declaration ("Contains Sulfites") where applicable
- Government health warning
- Appellation of origin (required in certain cases, e.g., grape variety named)
- Country of origin (imports)

### 2.3 Malt beverages (27 CFR part 7)
- Brand name
- Class and type designation
- Name and address
- Net contents
- Government health warning
- Alcohol content (disclosure rules vary; treat as expected unless known-exempt)

### 2.4 The ABV exceptions (do NOT hard-fail these)
- **Table wine:** wine 7% to 14% ABV may omit a numeric alcohol statement if the brand label
  carries the designation "table wine" or "light wine." Over 14% ABV, numeric ABV is mandatory.
- Beverage-type awareness matters: a missing ABV on a designated table wine is compliant, not
  a violation. A tool that flags it fails the judgment test.

## 3. Format-parsing notes (from the sample label)
- Alcohol content appears as `45% Alc./Vol. (90 Proof)`. Parse the percentage and, if present,
  proof. Cross-check proof = 2 x ABV for internal consistency.
- Net contents appears as `750 mL`. Parse magnitude + unit, normalize to mL for comparison.
- Comparison must be format-tolerant: `45%`, `45.0% Alc/Vol`, `ALC. 45% BY VOL` are the same value.

## Sources
- 27 CFR 16.21 (mandatory label information / warning text), Cornell LII and eCFR
- 27 CFR 16.22 (general requirements: type size, chars per inch, caps/bold, contrasting background)
- TTB, Modernization of Labeling and Advertising Regulations (T.D. TTB-176, eff. 2022) for parts 4/5/7
- TTB "Anatomy of a Wine Label" and distilled spirits mandatory label information guidance at ttb.gov
