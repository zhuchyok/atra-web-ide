-- Seed Initial Knowledge from ATRA Project Experiences
INSERT INTO domains (name, description) VALUES ('Trading', 'General trading strategies and rules');
INSERT INTO domains (name, description) VALUES ('Machine Learning', 'ML models, training, and feature engineering');
INSERT INTO domains (name, description) VALUES ('Backend', 'Python, Async, Performance, and Architecture');

-- Knowledge Nodes
-- 1. Sharpe Ratio Correction
INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
SELECT id, 'For 24/7 markets like Crypto, Sharpe Ratio must use sqrt(365) instead of sqrt(252). Current real Sharpe is 2.2-2.3.', 
'{"topic": "Sharpe Ratio", "fix_id": "11451158"}', 1.0, 'memories'
FROM domains WHERE name = 'Trading';

-- 2. ML Class Imbalance
INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
SELECT id, 'Always use compute_sample_weight in LightGBM to handle class imbalance (WIN vs LOSS). Improves F1/Precision/Recall by 5-10%.', 
'{"topic": "Machine Learning", "library": "LightGBM", "fix_id": "11451158"}', 1.0, 'memories'
FROM domains WHERE name = 'Machine Learning';

-- 3. Stateless Architecture
INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
SELECT id, 'Utility functions and indicators must be stateless. Pass state explicitly through parameters and return new state with results.', 
'{"topic": "Architecture", "principle": "Stateless"}', 1.0, 'repo_rules'
FROM domains WHERE name = 'Backend';

-- 4. Financial Precision
INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
SELECT id, 'Always use Decimal(str(value)) for financial calculations to avoid float rounding errors. Applicable to price, balance, profit, loss.', 
'{"topic": "Financial Accuracy", "type": "Decimal"}', 1.0, 'repo_rules'
FROM domains WHERE name = 'Backend';

-- 5. Reproducibility
INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
SELECT id, 'Backtests must be deterministic. Use ReproducibilityManager to initialize random seeds for random/numpy/torch.', 
'{"topic": "Reproducibility", "type": "Seed Management"}', 1.0, 'repo_rules'
FROM domains WHERE name = 'Trading';

-- 6. Adaptive Metadata Strategy
INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
SELECT id, 'Use JSONB for adaptive metadata storage. Index with GIN for performance. This allows project-agnostic scaling without breaking core schema.', 
'{"topic": "Architecture", "strategy": "Adaptive"}', 1.0, 'new_project_rules'
FROM domains WHERE name = 'Backend';

-- 7. Critic Loop Learning
INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
SELECT id, 'Implementation of autonomous feedback: System updates confidence_score based on user interaction success. Automatic refinement via background workers.', 
'{"topic": "AI", "feature": "Critic Loop"}', 1.0, 'new_project_rules'
FROM domains WHERE name = 'Machine Learning';

