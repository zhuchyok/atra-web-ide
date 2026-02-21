# Design Doc: Shadow Prompt Evolution (Singularity 15.0)

**Date:** 2026-02-20
**Status:** Approved
**Goal:** Implement an autonomous self-improvement loop for expert system prompts using local models and A/B shadow testing.

## 1. Overview
The system will automatically identify underperforming experts (based on feedback or errors), generate improved system prompts, and test them "in the shadow" of production traffic. A local LLM judge will compare production and shadow responses to determine if the mutation should be promoted to production.

## 2. Architecture

### 2.1 Database Schema
A new table `expert_mutations` will track the lifecycle of each prompt mutation.

```sql
CREATE TABLE IF NOT EXISTS expert_mutations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id UUID REFERENCES experts(id) ON DELETE CASCADE,
    mutated_prompt TEXT NOT NULL,
    base_version INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'shadow', -- shadow, promoted, rejected, archived
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    draw_count INTEGER DEFAULT 0,
    total_tests INTEGER DEFAULT 0,
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 Components

#### A. Mutation Generator (Nightly Learner)
- **Model:** `qwen2.5-coder:32b`
- **Trigger:** Nightly analysis of `interaction_logs`.
- **Logic:** Finds experts with negative feedback or high error rates. Generates a new `system_prompt` by analyzing past failures.

#### B. Shadow Mirror (`ai_core.py`)
- **Logic:** When a request is made to an expert with an active `shadow` mutation, the system returns the production response immediately but triggers a background task to generate a shadow response using the mutated prompt.

#### C. Shadow Evaluator (`shadow_evaluator.py`)
- **Model:** `qwq:32b` or `lfm2.5-thinking`
- **Logic:** Performs a "Blind Test" comparison between Prod and Shadow responses.
- **Criteria:** Accuracy, Utility, Brevity, Style adherence.

#### D. Promotion Engine
- **Logic:** Periodically checks mutation performance.
- **Threshold:** `total_tests >= 50` AND `win_rate > 65%`.
- **Action:** Updates `experts.system_prompt`, increments version, and sets mutation status to `promoted`.

## 3. Visualization (Canvas Mode)
The Dashboard's **Canvas** tab will feature:
- **Prompt Battle Monitor:** Real-time side-by-side comparison of responses.
- **Evolution Stats:** Win/Loss ratios and quality improvement trends.
- **Manual Control:** Buttons to manually promote or reject mutations.

## 4. Safety & Performance
- Shadow requests are executed with lower priority and in the background.
- Mutations are isolated per expert version.
- Max 1 active shadow mutation per expert at a time.
