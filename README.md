# Reddit Pain Radar

> **An evidence-backed Reddit problem discovery engine.**

Reddit Pain Radar uses **Scrapling** to crawl publicly accessible Reddit discussions, passes them through the **Cerebras API** with **Qwen3.8-27B** to extract genuine user friction, clusters problems with semantic embeddings, tracks volume growth trends, calculates deterministic opportunity scores, synthesizes product angles, and produces evidence-backed reports.

---

## 🎯 What It Does

Unlike generic "AI startup idea generators", Reddit Pain Radar answers:
> *"What problems are real people repeatedly experiencing, how painful are they, are they getting worse, how are people currently solving them, and is there evidence of an opportunity?"*

### Key Features
- **Scrapling-Powered Crawling**: Stealthy, reliable retrieval of public Reddit discussions without PRAW or paid API keys.
- **Two-Pass AI System**:
  - **PASS 1**: High-throughput classification and pain extraction via Cerebras Qwen3.8-27B with strict Pydantic JSON validation.
  - **PASS 2**: Deep opportunity synthesis and gap analysis on top-ranked problem clusters.
- **Semantic Clustering**: Groups varied phrasing of the same root pain into single clusters using `all-MiniLM-L6-v2` embeddings and hierarchical clustering.
- **Deterministic Scoring**: Transparent, auditable 0–100 opportunity formula combining frequency, discussion count, subreddit diversity, engagement, recency, growth, and workaround intensity.
- **Evidence-First Guarantee**: Every cluster retains verifiable Reddit URLs, quotes, and timestamps. Insufficiently evidenced ideas are flagged and filtered.

---

## 🏗️ Architecture & Data Flow

```text
Reddit (Public Web)
       │
       ▼
[ Scrapling Spider ] (StealthyFetcher, pagination, throttling)
       │
       ├─► data/raw/posts.jsonl & comments.jsonl
       ▼
[ SQLite DB ] (reddit_posts, reddit_comments)
       │
       ▼
[ Preprocessor ] (Removes spam, bots, promos; formats context)
       │
       ▼
[ PASS 1: Cerebras Qwen3.8-27B ] (Classifies real problems, workarounds, pain level)
       │
       ▼
[ SQLite: pain_signals ]
       │
       ▼
[ Semantic Embeddings ] (SentenceTransformers: all-MiniLM-L6-v2)
       │
       ▼
[ Agglomerative Clustering ] (Groups similar problems into problem_clusters)
       │
       ▼
[ Trend Detection & Deterministic Scoring ] (NEW, EMERGING, RISING, STABLE, DECLINING)
       │
       ▼
[ PASS 2: Cerebras Synthesis ] (Identifies solution gaps, workarounds, risks)
       │
       ▼
[ Reports Generator ]
       ├─► reports/top-problems.md
       ├─► reports/top-problems.csv
       └─► reports/top-problems.json
```

---

## 📋 Tech Stack & Python Version

- **Python**: `>= 3.12` (Tested on 3.12.10)
- **Scraping Engine**: `scrapling[all] >= 0.4.15`
- **AI Inference**: `cerebras-cloud-sdk >= 1.90.0` (model: `qwen-3.8-27b`)
- **Validation**: `pydantic >= 2.10.0`
- **Embeddings & Clustering**: `sentence-transformers >= 3.0.0`, `scikit-learn >= 1.4.0`
- **Database**: SQLite 3 (built-in)

---

## 🚀 Installation & Setup

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/shwetankrai12/reddit-scraping.git
cd reddit-scraping

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env`:

```env
CEREBRAS_API_KEY=your_cerebras_api_key_here
CEREBRAS_MODEL=qwen-3.8-27b
```

> **Note**: To run offline or run tests without a live Cerebras key, you can pass `--mock-ai` or set `CEREBRAS_MOCK_MODE=1`.

---

## ⚙️ Configuration (`config.yaml`)

Edit `config.yaml` to customize subreddits, search queries, scoring weights, and limits:

```yaml
crawler:
  subreddits:
    - SaaS
    - startups
    - Entrepreneur
    - smallbusiness
    - microsaas
    - sideproject
    - freelance
    - ecommerce
    - shopify
    - marketing
    - sales
    - accounting
    - realestate
    - productivity
    - webdev

  search_queries:
    - "looking for a tool"
    - "alternative to"
    - "I hate"
    - "frustrated"
    - "annoying"
    - "manual"
    - "workaround"

scoring_weights:
  frequency: 0.25
  unique_discussions: 0.15
  subreddit_diversity: 0.10
  engagement: 0.10
  recency: 0.10
  growth: 0.10
  workaround_intensity: 0.10
  existing_solution_dissatisfaction: 0.05
  purchase_switching_signals: 0.05
```

---

## 💻 CLI Usage

### Full End-to-End Run
Executes crawl → preprocess → PASS 1 analysis → clustering → scoring → PASS 2 synthesis → reports:

```bash
python main.py run --limit 300 --days 30
```

Specify custom subreddits:
```bash
python main.py run --subreddits SaaS,startups,smallbusiness --limit 100
```

### Modular Pipeline Commands

```bash
# 1. Crawl Reddit posts & comments
python main.py crawl --subreddits SaaS,startups --limit 50 --delay 1.0

# 2. Preprocess & run PASS 1 AI classification
python main.py analyze --concurrency 4

# 3. Cluster pain signals semantically
python main.py cluster

# 4. Calculate trend growth and opportunity scores
python main.py score --days 30

# 5. Generate Markdown, CSV, and JSON reports
python main.py report --top 15
```

---

## 📊 Scoring Methodology

Opportunity scores (0–100) are computed **deterministically in Python** (never generated arbitrarily by an LLM). Every component is transparent and audited:

| Component | Weight | Rationale |
|---|---|---|
| **Frequency** | 25% | How many times the problem was mentioned |
| **Unique Discussions** | 15% | Independent threads discussing this pain |
| **Subreddit Diversity** | 10% | Breadth across different communities |
| **Engagement** | 10% | Community resonance and upvote support |
| **Recency** | 10% | Freshness within the active analysis window |
| **Growth Rate** | 10% | Volume expansion vs. previous time window |
| **Workaround Intensity**| 10% | Rate of manual work (Excel, copy-pasting, etc.) |
| **Existing Tool Failure**| 5% | Dissatisfaction with incumbent solutions |
| **Purchase Signals** | 5% | Willingness to pay or switching intent |

### Trend Labels
- **RISING**: Growth $> +50\%$ over previous window
- **EMERGING**: Growth $+15\%$ to $+50\%$
- **STABLE**: Growth $-20\%$ to $+15\%$
- **DECLINING**: Growth $< -20\%$
- **NEW**: Recent problem with limited historical comparison baseline

---

## 📁 Output Reports

Reports are automatically saved in `reports/`:
- `reports/top-problems.md`: Clean, executive markdown summary with quotes and evidence links.
- `reports/top-problems.csv`: Tabular format with all quantitative rates and scores.
- `reports/top-problems.json`: Full machine-readable payload including PASS 2 synthesis.

### Example Markdown Output:

```markdown
==================================================
REDDIT PAIN RADAR
==================================================

#1 Small agencies struggle to collect client approvals

Pain Score: 87/100
Trend: RISING
Mentions: 43
Discussions: 31
Subreddits: 8
Workaround Rate: 72%
Existing Solution Failure: 54%
Purchase Signal: 18%

TARGET USER
Small marketing/design agencies

CURRENT WORKAROUND
WhatsApp + email + spreadsheets

WHY IT HURTS
Scattered feedback channels cause delayed project delivery and unbilled scope creep.

EVIDENCE

1. https://www.reddit.com/r/SaaS/comments/...
2. https://www.reddit.com/r/startups/comments/...
3. https://www.reddit.com/r/freelance/comments/...

--------------------------------------------------
```

---

## 🛡️ Responsible Crawling & Ethics

Reddit Pain Radar adheres to ethical, non-invasive data collection:
- **Public Content Only**: Only retrieves publicly accessible posts and comments.
- **No Private Access**: Never bypasses logins, paywalls, or private subreddits.
- **Rate-Limiting**: Built-in request pacing (`--delay 1.0` seconds) and exponential backoff.
- **Anonymity**: Usernames are not indexed or used as core system identifiers.

---

## 🧪 Testing

Run unit and integration tests with `pytest`:

```bash
pytest -v
```

The test suite covers:
- Reddit DOM parsing (`test_crawler_parsing.py`)
- Text cleaning and spam/promo filtering (`test_preprocessing.py`)
- Pydantic AI schemas & repair mechanisms (`test_ai_schemas.py`)
- Semantic problem clustering (`test_clustering.py`)
- Deterministic scoring calculations (`test_scoring.py`)
- Time-window trend classification (`test_trends.py`)

---

## 🔧 Troubleshooting

- **Cerebras Connection Issues**: Verify `CEREBRAS_API_KEY` is set in your `.env`. Test with `--mock-ai` to verify pipeline integrity independently.
- **Scrapling Engine**: Ensure `scrapling[all]` and browser binaries are initialized. `StealthyFetcher` handles modern Reddit JavaScript components seamlessly.
- **Windows UTF-8 Encoding**: `main.py` explicitly reconfigures stdout for UTF-8 to prevent console encoding issues with special characters and emojis.
