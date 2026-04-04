# Company Intelligence Metrics Standard — Nexus Agent

## Overview
20 industry-standard numeric metrics for competitive intelligence analysis.
Based on frameworks from: Gartner CI, CB Insights, Bloomberg Intelligence,
PitchBook, and McKinsey Growth Analytics (2024-2026).

Each metric specifies: definition, unit, calculation strategy, data sources, and confidence guidance.

---

## Metric Definitions

### Growth & Scale Metrics

**M01 — Employee Growth Rate (6-month)**
- **Definition:** % change in headcount over the past 6 months
- **Unit:** Percentage (%)
- **Calculation:** `(current_headcount - headcount_6mo_ago) / headcount_6mo_ago × 100`
- **Sources:** LinkedIn headcount, job posting velocity, Crunchbase, company press releases
- **Proxy if exact unknown:** Count LinkedIn employee range change (e.g. "501-1000" → "1001-5000" = +growth signal)
- **Benchmark:** >20% = hypergrowth, 5-20% = healthy growth, <5% = flat/declining

**M02 — Job Posting Velocity**
- **Definition:** Number of new job postings in the past 30 days
- **Unit:** Count (jobs/month)
- **Calculation:** Count active job listings on LinkedIn/Indeed/Greenhouse/Lever/Workable
- **Sources:** LinkedIn Jobs, Indeed, company careers page, Builtin
- **Signal:** Spikes in specific departments (e.g. +15 ML engineers) indicate strategic investment areas

**M03 — Hiring Focus Score**
- **Definition:** % of job postings in the company's top hiring department
- **Unit:** Percentage (%)
- **Calculation:** `(jobs_in_top_dept / total_jobs) × 100`
- **Sources:** LinkedIn job categories, job titles parsed by department
- **Interpretation:** >40% in one dept = strategic pivot signal

**M04 — Revenue Estimate (ARR/Revenue)**
- **Definition:** Estimated annual recurring revenue or total revenue
- **Unit:** USD Millions
- **Calculation:** Use disclosed figures; if private: headcount × revenue-per-employee benchmark for sector
  - SaaS: $150k-$300k revenue/employee
  - Fintech: $200k-$500k revenue/employee
  - AI/ML: $100k-$250k revenue/employee
- **Sources:** SEC filings (public), Crunchbase, PitchBook, Glassdoor estimates, press releases

**M05 — Funding Total**
- **Definition:** Total capital raised to date across all rounds
- **Unit:** USD Millions
- **Calculation:** Sum of all disclosed funding rounds
- **Sources:** Crunchbase, PitchBook, SEC Form D filings, press releases
- **Note:** Flag as ⚠️ Low confidence if no public disclosure available

**M06 — Funding Runway Estimate**
- **Definition:** Estimated months of operation remaining at current burn rate
- **Unit:** Months
- **Calculation:** `last_round_size / estimated_monthly_burn`
  - Monthly burn proxy: `(headcount × avg_salary_loaded_cost) / 12`
  - Loaded cost multiplier: 1.25-1.4× base salary
- **Sources:** Last funding round size (Crunchbase), LinkedIn headcount, Glassdoor salaries

---

### Market Position Metrics

**M07 — Web Traffic Estimate (Monthly Visits)**
- **Definition:** Estimated monthly unique website visitors
- **Unit:** Millions of visits/month
- **Calculation:** Use SimilarWeb/SEMrush estimates; if unavailable, infer from Alexa rank tier
- **Sources:** SimilarWeb, SEMrush, Ahrefs, web search snippet metrics
- **Benchmark:** >10M = category leader, 1-10M = significant player, <500k = niche

**M08 — Domain Authority / SEO Score**
- **Definition:** Domain authority score (0-100) indicating organic search strength
- **Unit:** Score (0-100)
- **Calculation:** Moz DA score or Ahrefs DR score
- **Sources:** Moz, Ahrefs, SEMrush (check via web search for cached scores)

**M09 — App Store Rating**
- **Definition:** Average user rating across iOS App Store and Google Play
- **Unit:** Score (1.0-5.0)
- **Calculation:** `(ios_rating × ios_reviews + play_rating × play_reviews) / (ios_reviews + play_reviews)`
- **Sources:** App Store, Google Play — search company name + app
- **Benchmark:** >4.5 = excellent, 4.0-4.5 = good, <4.0 = significant UX issues

**M10 — Social Media Follower Count**
- **Definition:** Total followers across primary professional social channels
- **Unit:** Count (thousands)
- **Calculation:** Sum of LinkedIn followers + Twitter/X followers
- **Sources:** LinkedIn company page, Twitter/X profile
- **Note:** Report LinkedIn and Twitter separately for quality signal

**M11 — GitHub Activity Score**
- **Definition:** Composite of GitHub stars, forks, and recent commit frequency (tech companies only)
- **Unit:** Score (derived)
- **Calculation:** `(stars × 0.4) + (forks × 0.3) + (commits_last_30d × 30 × 0.3)`; normalise to 0-100 vs sector peers
- **Sources:** GitHub public repos, GitHub API, libraries.io
- **Skip if:** Company has no public GitHub presence (mark N/A)

---

### Customer & Sentiment Metrics

**M12 — Review Score (B2B/B2C)**
- **Definition:** Average rating on primary review platform
- **Unit:** Score (1.0-5.0)
- **Calculation:** Use G2 (B2B SaaS), Capterra (SMB software), Trustpilot (consumer), or Glassdoor (employer brand)
- **Sources:** G2.com, Capterra, Trustpilot, Glassdoor
- **Benchmark (G2):** >4.5 = top tier, 4.0-4.5 = competitive, <4.0 = significant churn risk

**M13 — Review Volume (30-day)**
- **Definition:** Number of new reviews posted in the past 30 days
- **Unit:** Count (reviews/month)
- **Calculation:** Check review platform for "recent" reviews and date-filter
- **Sources:** G2, Trustpilot, Glassdoor
- **Signal:** Sudden spike = major product launch or PR event; sudden drop = user disengagement

**M14 — Sentiment Score**
- **Definition:** Net positive vs negative sentiment in public mentions
- **Unit:** Score (-100 to +100, NPS-style)
- **Calculation:** `((positive_mentions - negative_mentions) / total_mentions) × 100`
  - Classify mentions from news, Reddit, Twitter, review snippets as positive/negative/neutral
  - Use LLM to classify each source passage found during research
- **Sources:** News search results, Reddit, Twitter/X, review snippets

**M15 — Employee Satisfaction Score**
- **Definition:** Glassdoor overall company rating
- **Unit:** Score (1.0-5.0)
- **Calculation:** Direct Glassdoor rating; also note CEO approval % if available
- **Sources:** Glassdoor company page
- **Benchmark:** >4.0 = strong culture/retention, <3.5 = high attrition risk signal

---

### Technology & Innovation Metrics

**M16 — Patent Filing Count (2-year)**
- **Definition:** Number of patents filed or granted in the past 24 months
- **Unit:** Count
- **Calculation:** Search Google Patents, USPTO, EPO for company name; filter by date
- **Sources:** Google Patents (patents.google.com), USPTO, Espacenet
- **Note:** R&D-intensive companies only; skip for services/marketplaces (mark N/A)

**M17 — Technology Stack Breadth**
- **Definition:** Number of distinct technologies detected in company's product/infrastructure
- **Unit:** Count
- **Calculation:** Count distinct tech categories from BuiltWith/Wappalyzer scan of company website
- **Sources:** BuiltWith.com, Wappalyzer, Stackshare
- **Interpretation:** High count = complex/mature stack; low = early-stage or monolith

**M18 — Product Release Frequency**
- **Definition:** Number of product updates/releases in the past 6 months
- **Unit:** Count (releases/6mo)
- **Calculation:** Count entries in public changelog, release notes, app store update history, or GitHub releases
- **Sources:** Company changelog page, GitHub releases, App Store version history, Product Hunt

---

### Risk & Compliance Metrics

**M19 — News Mention Volume (30-day)**
- **Definition:** Number of distinct news articles mentioning the company in the past 30 days
- **Unit:** Count (articles/month)
- **Calculation:** Web search `"{company_name}" site:news.google.com OR site:reuters.com OR site:techcrunch.com` last 30 days; count results
- **Sources:** Google News, Reuters, TechCrunch, Bloomberg, industry publications
- **Signal:** Very high volume = PR event (positive or negative); trending downward = losing mindshare

**M20 — Regulatory/Legal Risk Score**
- **Definition:** Count of active regulatory actions, lawsuits, or compliance flags
- **Unit:** Count
- **Calculation:** Search for: `"{company_name}" lawsuit OR "regulatory action" OR "FTC" OR "GDPR fine" OR "SEC"` in past 12 months
- **Sources:** PACER (US court filings), SEC EDGAR, news search
- **Interpretation:** 0 = clean, 1-2 = monitor, 3+ = significant risk flag
- **Note:** Always flag source and date for legal/regulatory claims

---

## Metric Output Format

When the metrics agent calculates these, output as structured JSON:

```json
{
  "company_id": 1,
  "report_id": "uuid",
  "calculated_at": "ISO datetime",
  "metrics": [
    {
      "code": "M01",
      "name": "Employee Growth Rate (6-month)",
      "value": 23.5,
      "unit": "%",
      "confidence": "medium",
      "source": "LinkedIn headcount, Crunchbase",
      "note": "Based on headcount range change from 501-1000 to 1001-5000"
    }
  ]
}
```

**Confidence levels:**
- `high` — sourced from official/verified data (SEC filing, official press release)
- `medium` — sourced from reputable third-party (Crunchbase, G2, LinkedIn)
- `low` — estimated/inferred with proxy calculation
- `unavailable` — insufficient data to calculate

---

## Calculation Priority

When research data is limited, prioritise metrics in this order:
1. M01, M02, M07, M12 — most commonly available from public web
2. M04, M05, M10, M15 — often available for funded companies
3. M14, M19, M20 — always calculable via news/review search
4. M06, M08, M09, M11, M13, M16, M17, M18 — best-effort, mark unavailable if no data

---

*Last updated: 2026-04. Based on: CB Insights Company Scorecard, Gartner CI Metrics Framework, PitchBook Analyst Methodology, Bloomberg Intelligence KPIs.*
