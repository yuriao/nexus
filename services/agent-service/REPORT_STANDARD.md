# Competitive Intelligence Report Standard — Nexus Agent

## Overview

This guideline defines the industry-standard structure for all Nexus competitive intelligence reports.
Based on frameworks from Gartner, McKinsey, SCIP (Strategic and Competitive Intelligence Professionals),
and best practices from leading CI practitioners (2024-2026).

---

## Report Structure (Required Sections in Order)

### 1. Executive Summary
**Length:** 150-250 words (3 tight paragraphs max)

- **Paragraph 1 — Situation:** What is the company's current market position? One compelling hook stat or finding.
- **Paragraph 2 — Key Findings:** The 3 most important insights (McKinsey Rule of 3). Be specific.
- **Paragraph 3 — Strategic Implication:** What should the reader DO with this information? One clear call-to-action.

> ✅ Start with the most important finding, not background.
> ❌ Do NOT start with "This report analyzes..." or "In this report we will..."

---

### 2. Company Snapshot
**Format:** Structured facts block (not paragraphs)

- **Founded / HQ / Employees / Revenue (est.)**
- **Core Products / Services**
- **Primary Markets & Customer Segments**
- **Business Model** (SaaS / marketplace / hardware / etc.)
- **Key Leadership** (CEO + 1-2 notable executives)
- **Funding Stage / Ownership** (public / private / PE-backed)

---

### 3. Market Position & Competitive Landscape
**Length:** 200-350 words

- Where does this company sit in the market? (leader / challenger / niche / disruptor)
- Who are the top 3 direct competitors? How does this company differentiate?
- What is its estimated market share or growth trajectory?
- What is the **competitive moat** (if any)? (brand, data, network effects, switching costs, IP)

---

### 4. SWOT Analysis
**Format:** 4-quadrant table or clearly labelled lists

| Strengths | Weaknesses |
|-----------|------------|
| Internal advantages | Internal gaps/vulnerabilities |

| Opportunities | Threats |
|---------------|---------|
| External tailwinds | External risks/pressures |

- **Minimum 3 points per quadrant**
- All points must be **specific and evidence-backed** — no generic statements like "strong brand"
- Bad: "Has a strong brand" → Good: "Brand NPS of 72 (industry avg 45), per customer surveys"

---

### 5. Key Findings
**Format:** Numbered list, 5-8 findings

Each finding must follow this pattern:
> **[Finding title]:** [Specific observation]. [Why it matters / strategic implication].

Examples:
> **Aggressive Talent Acquisition:** Anthropic added 340 ML engineers in Q1 2026, tripling its safety team — signalling a major pre-launch push for Claude 4.
> **Pricing Pressure:** Claude API prices dropped 40% in 6 months while usage grew 3x — indicating a land-grab strategy prioritising volume over margin.

---

### 6. Opportunities (for competitors / market participants)
**Format:** Numbered list, 3-5 opportunities

Each opportunity:
- Must be **actionable** — what can a competitor or investor DO?
- Should specify **timeframe** (immediate / 6-month / 12-month+ window)
- Should estimate **confidence level** (High / Medium / Low)

Template:
> **[Opportunity]:** [Description]. **Timeframe:** [X months]. **Confidence:** [H/M/L].

---

### 7. Risks & Threats
**Format:** Numbered list, 3-5 risks

Each risk:
- Must specify **likelihood** (High / Medium / Low)
- Must specify **impact** if realised (High / Medium / Low)
- Should suggest a **mitigation** where possible

Template:
> **[Risk]:** [Description]. **Likelihood:** [H/M/L]. **Impact:** [H/M/L]. **Mitigation:** [suggestion].

---

### 8. Strategic Predictions (6-12 Month Outlook)
**Format:** Numbered list, 3-5 predictions

Each prediction:
- Must be **falsifiable** — specific enough to be proved right or wrong
- Must include a **confidence percentage** (e.g. 70%)
- Must cite the **signal/evidence** behind the prediction

Template:
> **[Prediction]:** [Specific outcome] by [timeframe]. **Confidence:** [X]%. **Signal:** [what data/trend supports this].

Bad: "The company will grow" → Good: "Anthropic will launch a dedicated enterprise tier by Q3 2026 (75% confidence) — signalled by 3 enterprise-focused job postings in Feb 2026 and CEO comments at Davos."

---

### 9. Data Sources & Methodology
**Format:** Brief bulleted list

- List all data sources used (web search, news, job postings, SEC filings, etc.)
- State the data collection date range
- Note any significant data gaps and how they affected confidence
- State overall report confidence: **High / Medium / Low** with brief justification

---

## Formatting Rules

1. **Headers:** Use `##` for main sections, `###` for subsections
2. **Emphasis:** Use **bold** for key terms and findings
3. **Numbers:** Always prefer specific numbers over vague qualifiers ("40% drop" not "significant drop")
4. **Tone:** Professional, direct, third-person. No hedging phrases like "it seems" or "perhaps"
5. **Length:** Full report should be 800-1,500 words (not counting the SWOT table)
6. **No filler:** Every sentence must add information. Remove any sentence that is just restating another.
7. **Confidence flags:** Use `⚠️ Low confidence:` prefix for any claim that lacks strong sourcing

---

## Quality Checklist (Critic must verify all)

- [ ] Executive summary leads with most important finding (not background)
- [ ] All SWOT points are specific and evidence-backed (no generic statements)
- [ ] Each Key Finding states both the observation AND the implication
- [ ] Each Opportunity includes timeframe and confidence level
- [ ] Each Risk includes likelihood, impact, and mitigation
- [ ] Each Prediction is falsifiable with a confidence % and supporting signal
- [ ] Report contains at least one specific number/metric per section
- [ ] No section is just restating another section
- [ ] Sources are listed in Methodology section
- [ ] Overall report length is 800-1500 words

---

## Anti-Patterns to Avoid

| ❌ Bad | ✅ Good |
|--------|---------|
| "Strong leadership team" | "CEO Sarah Chen has 15 years in enterprise SaaS; led Salesforce's APAC expansion 2018-2022" |
| "Growing market opportunity" | "TAM of $47B by 2027 (Gartner 2025), company currently at ~2% penetration" |
| "May face regulatory challenges" | "EU AI Act Article 12 compliance required by Aug 2026; company has no published compliance roadmap" |
| "Significant competitive advantage" | "Only vendor with SOC 2 Type II + ISO 27001 dual certification in this segment" |
| Predictions without confidence | "Will launch mobile app in Q2 2026 (80% confidence — 4 mobile engineer job postings, Jan 2026)" |

---

*Last updated: 2026-04. Based on: SCIP CI Report Framework v3, McKinsey Strategic Intelligence Standards, Gartner CI Best Practices Guide.*
