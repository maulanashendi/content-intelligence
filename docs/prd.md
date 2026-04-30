# PRD: Editorial Intelligence Platform

## 1. Context

Tempo's strategy is not about being the fastest, but about delivering the most comprehensive information. A topic worth covering must be assessed as worthy of being written — not a fleeting event that rises and disappears quickly. Tempo's position is strategic because it holds a higher level of trust compared to other media, and our job is to build on that trust by delivering the clearest information from multiple perspectives. Depth of reporting is essential.

Today, the decision of which topics to cover relies entirely on editorial intuition. There are no data-driven tools to support analysis. Many articles get written but underperform on views and conversion rate.

What's needed: a tool that tracks **from the outside** (not from the inside — internal article performance is already handled by a separate internal dashboard). The focus: how topics that are gaining traction across competitors and trends can help us choose subjects that are **not yet covered by us but worth writing.**

Technical approach: topic grouping via clustering. So we can capture news that hasn't been covered yet, or topics that have been written but underperformed — making them candidates for a rewrite with a fresh angle.

---

## 2. Users & daily decisions

### Primary persona: Maulana — Content Editor, Economy Desk

Every morning at 9 AM, Maulana decides on 2-3 topics his team will write that day. He needs to know:

1. What topics are trending in our niche (economy)?
2. Has the team covered this topic recently?
3. Is the topic already saturated in the market (most competitors have already covered it)?

A fourth question naturally arises during Maulana's evaluation — _"could this content become a paid premium piece?"_ — but this is not a feature built into the app. It's a **side benefit** that emerges when Maulana reviews the raw data (number of competitors, angles already explored). The decision stays with Maulana; the system provides no scoring or flagging.

### Secondary persona: Editorial Desk Head

The desk head uses the **same app** as Maulana. His role within the app is narrow: viewing **deferred topics** — clusters that are trending but haven't been picked up by the team for several days. From there, he can talk to the team about the agenda for the next day.

The desk head's other activities (reviewing internal article performance, team coordination, daily evaluation) **happen outside the app**. The app does not build features for those because a separate internal dashboard already exists and most coordination happens in Slack or meetings.

---

## 3. Solution

An internal dashboard that:

1. Each morning, automatically ingests the latest articles from competitor sources (RSS), Tempo's internal sitemap (to detect "already written"), and Google Trends signals.
2. Groups those articles into "topics" (clusters) based on semantic similarity.
3. Computes a "worth writing" score per topic based on: how fast the topic is growing, how many competitors have covered it, and whether our team has covered it in the last 30 days.
4. Surfaces the top 10 topics that **we haven't written about in the last 30 days**, sorted by velocity.
5. Provides per-topic detail: competitor articles (title + first paragraph + source + publish date) and a brief reference to internal articles that previously covered similar topics.

**What the app does not do:** display performance metrics for internal articles (clicks, impressions, Google position). That's the domain of a separate internal dashboard. This app focuses on one thing: **finding topics worth writing about, through clustering.**

Maulana opens the dashboard → sees 10 topics → clicks 2-3 interesting ones for detail → if needed, opens the other dashboard in a separate tab to check internal performance → 5-minute team discussion in Slack → starts writing. Total decision time: 10-15 minutes, instead of 1 hour.

---

## 4. Happy path

### 06:00 — Background processing

The system automatically:

- Ingests RSS from competitor sources: detik.com, kompas.com, tirto.id, cnnindonesia.com, kontan.co.id (for the economy desk).
- Ingests Tempo's internal sitemap for economy desk articles published yesterday (to detect "already written").
- Ingests Google Trends keywords for Indonesian economy.
- Generates embeddings for new articles.
- Runs full-scan HDBSCAN clustering.
- Computes `cluster_insight` (velocity, novelty, coverage, recommendation).
- Updates the `is_current` flag on the cluster table.

### 09:00 — Maulana opens the dashboard

The system shows 10 clusters that:

- Come from the most recent clustering run (this morning).
- Have a recommendation of `trending` or `worth_writing`.
- Have no internal Tempo article published in the last 30 days.
- Are sorted by `trend_velocity` descending.

Display:

| Cluster               | Velocity | Articles | Sources       | Sample Headline                                       |
| --------------------- | -------- | -------- | ------------- | ----------------------------------------------------- |
| Q2 rice price hike    | 0.87     | 14       | 6 competitors | "Premium Rice Tops Rp18,000/kg at Wholesale Market"   |
| New fintech tax rules | 0.73     | 9        | 4 competitors | "OJK Issues New Online Lending Rules, Effective July" |
| BPJS deficit 2026     | 0.65     | 11       | 5 competitors | "BPJS Deficit Hits Rp20T, Premiums to Rise?"          |
| ...                   | ...      | ...      | ...           | ...                                                   |

### 09:03 — Maulana clicks into a cluster

Maulana clicks "Q2 rice price hike." He wants to evaluate: is this worth writing for Tempo, and if so, from what angle?

The system shows **competitor articles in this cluster**, sorted by publish date:

| Headline                                         | Source           | Published | First Paragraph                                                                              |
| ------------------------------------------------ | ---------------- | --------- | -------------------------------------------------------------------------------------------- |
| "Premium Rice Tops Rp18,000/kg"                  | detik.com        | 28 Apr    | "Premium rice prices at the Cipinang wholesale market have risen 12% over the past month..." |
| "Bulog: Rice Stock Safe Through June"            | kompas.com       | 27 Apr    | "Bulog's CEO stated that national rice stock remains sufficient..."                          |
| "Farmers Complain About Suppressed Grain Prices" | tirto.id         | 27 Apr    | "Amid surging retail rice prices, farmers are instead..."                                    |
| "Rice Imports: Solution or Problem?"             | cnnindonesia.com | 26 Apr    | "The government is opening the option to import 500,000 tons of rice to..."                  |
| ... (16 more articles)                           |                  |           |                                                                                              |

`first_paragraph` is shown so Maulana can quickly scan the angles competitors have already explored — the essence of Tempo's "complete from multiple perspectives" strategy.

### 09:08 — Maulana decides

From the data above, Maulana sees:

- Competitors have covered: retail prices (detik), Bulog stock (kompas), farmers (tirto), imports (cnn).
- No one has covered the lower-middle-class consumer angle (household expenditure burden).

For context on Tempo's related internal article performance, Maulana **opens the separate internal dashboard** in another tab (out of scope for this app).

Decision: write a deep article from the angle "impact on the lower-middle class," using BPS household expenditure data and consumer interviews.

Maulana coordinates with the team in Slack. **There is no app interaction in this step** — no "claim" button, no "mark as taken." Chat-based coordination is enough for a small team.

### 14:00 — Desk head checks deferred topics

The desk head opens the same app as Maulana and looks at **deferred topics**: clusters that are trending but have no internal article in the last 7 days. Sorted by velocity, with extra info: how many days the topic has been trending without coverage.

From there the desk head can see: "Topic X has been trending for 3 days, competitors already have 8 articles, we haven't written anything." He communicates with the team via Slack as input for tomorrow's agenda.

The desk head's other activities (reviewing today's published articles, early SEO assessments) **happen outside this app** — in the existing internal dashboard.

### 16:00 — Maulana publishes the article

No system interaction.

### Next morning 06:00 — Auto-detect

Ingestion picks up the Tempo article via internal RSS → embedding → joins cluster "Q2 rice price hike" in the daily clustering run → cluster automatically drops out of the recommendation list because the "internal article < 30 days" filter is satisfied.

---

## 5. Success metrics (review 2 weeks after launch)

Metrics are measured via **interviews/surveys with Maulana and the desk head** two weeks after launch. There is no automated tracking inside the app because there are no claim or user-action features.

- **Decision time:** Maulana's average daily topic decision takes < 15 minutes (from ~1 hour).
- **Recommendation quality:** ≥ 50% of the topics Maulana picked in the last 2 weeks come from the dashboard's top 10. Measured via a recall-based interview with Maulana.
- **System health:** ingestion + clustering run without manual intervention for 2 consecutive weeks.

If any metric isn't met after 2 weeks, evaluate: is the issue data quality (clusters not accurate), label quality (hard to read), or dashboard UX?

---

## 6. What we will NOT build in MVP

Deferred until users explicitly ask:

- **Internal article performance metrics & analytics.** Already handled by a separate internal dashboard. This app does not show clicks, impressions, Google position, or anything similar. If Maulana or the desk head needs that data, they open the other dashboard in a separate tab.
- **A dedicated desk-head dashboard with team metrics** (today's articles, yesterday's performance). Those activities happen outside this app.
- **Cluster lineage / cross-time topic tracking.** No "topic X velocity over the last 30 days" chart. Each clustering run stands alone. Add only if users request historical tracking.
- **Manual claim / dismiss cluster.** No "I'll write this" button. Coordination via Slack. Add only if the team grows beyond 5 people or real conflicts arise.
- **Push notifications when topics start trending.** No email/Slack alerts. Maulana checking the dashboard each morning is sufficient.
- **Desk-head notifications for topics deferred > 3 days.** The desk head already opens the app daily — redundant.
- **Similar article search for writers.** Not Maulana's problem. Writers use Google during research.
- **Auto-categorization of content type** (news vs. evergreen vs. tutorial). Editors already know the context without system help.
- **A composite "worth writing" score as a single number.** Show velocity, novelty, coverage as raw values. Editors trust raw numbers more.
- **Burst detection** (sudden hot topics). Velocity is a sufficient proxy. Add only if Maulana complains about "missing momentum."
- **Per-competitor breakdown** ("TechCrunch yes, The Verge no"). `member_count` and `competitor_count` per cluster are sufficient signals.
- **HNSW index for vector similarity search.** No similarity queries in the happy path. Add when a future feature requires it.
- **Auto angle detection.** Too complex, requires an LLM, high misclassification risk. Maulana reads competitor `first_paragraph` himself.
- **Auto premium scoring.** Editorial judgment — don't automate it. Maulana decides from raw data.
- **Tracking competitor views/engagement.** Not reliably available at reasonable cost (would require BuzzSumo/Semrush). Not essential for Tempo's "depth, not speed" strategy.

---

## 7. Open questions

Not yet decided, requires confirmation before or during development:

1. **The "already written" window — 30 days, or shorter?** Depends on topic lifecycle in the economy niche. We need to inspect 20 sample clusters for the date distribution before locking the number.
2. **Cluster label quality.** Labels are auto-generated (LLM or top-keyword?). If labels are poor ("economy, price, market"), Maulana has to click each cluster — UX breaks down. Needs testing before launch with 3-5 sample clusters.
3. **Clustering frequency — is daily enough?** If Maulana asks for more real-time (hourly), we need to evaluate compute cost.
4. **How many competitor sources should we ingest?** Start with the 5 curated RSS feeds in section 4. Evaluate after 2 weeks whether to add or drop sources.
5. **Do we need to deduplicate syndicated competitor articles?** The same article appearing across multiple sites would inflate `member_count` falsely. Unclear how often this happens in the economy niche.

---

## 8. Technical notes

Implementation details (database schema, API, infrastructure) are not part of this PRD but have been designed and reviewed separately. The schema supports 100% of the happy path in section 4 with a lean set of core queries. No schema changes are required for MVP launch.

---

## A note on reading this PRD

This document is intentionally short (~3 pages). When the question "what about feature X?" comes up, check section 6 first — if X is in "what we won't build," that's a deliberate decision, not an oversight. If X isn't in section 6 and isn't in the happy path either, that's a feature-creep signal — discuss before adding.
