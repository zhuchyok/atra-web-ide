# Design: Victoria Efficiency & Token Savings Dashboard (Singularity 21.2)

## 1. Context & Problem

We have successfully implemented **Council Mode** to keep reasoning tasks local. Now we need to visualize the impact:

- How many tokens are processed locally vs cloud?
- What is the monetary value of these savings (ROI)?
- Are there any "leakages" to the cloud for expert tasks?

## 2. Proposed Design: "Victoria Efficiency"

### 2.1. Metrics Strategy (Prometheus)

We will use the existing `llm_tokens_total` and `llm_requests_total` metrics but ensure they are correctly populated for the `local` provider.

- **Provider**: `local` (MLX/Ollama) vs `cloud` (Cursor/OpenAI/Anthropic).
- **Model**: Specific local model names (e.g., `victoria-wisdom-30b`).

### 2.2. Monetary Valuation (ROI)

We will use **Claude 3.5 Sonnet** pricing as the benchmark for local savings:

- **Input**: $3.00 per 1M tokens.
- **Output**: $15.00 per 1M tokens.
- **Mac Studio Cost**: $5,000 (M4 Max base).

### 2.3. Dashboard Layout (Grafana)

- **Row 1: Key Performance Indicators (KPIs)**
  - `Stat`: Total Savings ($) - Cumulative since deployment.
  - `Stat`: 24h Savings ($) - Savings in the last 24 hours.
  - `Gauge`: Local Autonomy % - Goal > 95% for reasoning tasks.
- **Row 2: Token Distribution**
  - `Pie Chart`: Local vs Cloud Tokens.
  - `TimeSeries`: Tokens Processed per Hour (Stacked).
- **Row 3: ROI & Financials**
  - `Stat`: Mac Studio ROI % - (Total Savings / $5,000) \* 100.
  - `TimeSeries`: Cumulative Savings vs Hardware Cost.

## 3. Implementation Plan

1.  **Update `ai_core.py`**: Ensure `record_llm_request` is called for all local successes.
2.  **Update `prometheus_metrics.py`**: Add any missing labels or specific local counters if needed.
3.  **Create Grafana Dashboard**: Provision `victoria-efficiency.json`.
4.  **Update `MASTER_REFERENCE.md`**: Document the new monitoring standard.

## 4. Success Criteria

- [ ] Dashboard shows real-time local token consumption.
- [ ] Monetary savings are calculated automatically based on Claude 3.5 prices.
- [ ] ROI gauge correctly reflects the hardware amortization.
