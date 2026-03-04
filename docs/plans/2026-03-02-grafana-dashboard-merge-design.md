# Design: UI/UX Optimized Token Savings Integration (Singularity 21.3)

## 1. Context & Problem

We need to merge the "Victoria Efficiency" metrics into the main `ATRA Knowledge OS Dashboard` (`atra-dashboard.json`) with a focus on high-quality UI/UX.

## 2. UI/UX Design Strategy (The "Golden Ratio" of Monitoring)

### 2.1. Hero Section (Top KPI Row)

- **Savings ($)**: Large Stat panel with a green trend line. This is the first thing the user sees.
- **ROI %**: Circular Gauge next to Savings. Visualizes how close the Mac Studio is to paying for itself.
- **Local Autonomy**: Small sparkline showing the percentage of local vs cloud traffic.

### 2.2. Integrated Token Panel (Middle Row)

- **Token Flow**: Stacked Area chart showing `Local Tokens` vs `Cloud Tokens`.
- **Legend**: Clear, color-coded legend (Local = Green, Cloud = Amber).

### 2.3. Detailed Breakdown (Collapsible Row)

- A new row named "Financial & Efficiency Details" containing:
  - Table of savings per model.
  - Latency impact of local vs cloud.

## 3. Implementation Plan

1.  **Modify `atra-dashboard.json`**:
    - Add the Hero Section at the top (y=0).
    - Shift existing panels down.
    - Update Panel #3 (Tokens) to include the new local/cloud metrics.
2.  **Clean up**: Delete `grafana/dashboards/victoria-efficiency.json`.
3.  **Verify**: Ensure the JSON is valid and the UID remains `atra-knowledge-os`.

## 4. Success Criteria

- [ ] Dashboard is visually balanced and professional.
- [ ] Key financial metrics are visible without scrolling.
- [ ] No duplicate dashboards in the repository.
