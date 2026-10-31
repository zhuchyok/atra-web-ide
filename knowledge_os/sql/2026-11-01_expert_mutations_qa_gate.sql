-- ============================================================================
-- 2026-11-01: QA-gate for expert_mutations promotions
--
-- Problem: 328 of 336 rows with status='promoted' have total_tests=0
-- (promoted blindly), and some mutated_prompt values contain leaked
-- LLM instruction markers ("ОТВЕТЬТЕ ТОЛЬКО", "ТЕКСТ НОВОГО ПРОМПТА", ...).
--
-- Fix: BEFORE trigger that forbids transitioning a row to status='promoted'
-- unless total_tests >= 10. The check fires only on NEW transitions
-- (NEW.status='promoted' AND OLD.status IS DISTINCT FROM 'promoted'),
-- so updates to already-promoted legacy rows (e.g. archiving them later)
-- are not affected.
--
-- NOTE: leak-marker validation lives in application code
-- (app/promotion_engine.py :: mutation_passes_qa_gate) because full-text
-- substring matching for Cyrillic markers is better handled in Python;
-- the DB-level gate enforces the hard statistical floor (total_tests).
--
-- DO NOT run against the live database without review.
-- Apply manually:  psql $DATABASE_URL -f knowledge_os/sql/2026-11-01_expert_mutations_qa_gate.sql
-- ============================================================================

CREATE OR REPLACE FUNCTION enforce_expert_mutations_qa_gate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Only guard NEW transitions into 'promoted'; leave already-promoted
    -- legacy rows (and transitions out of 'promoted') untouched.
    IF NEW.status = 'promoted' AND OLD.status IS DISTINCT FROM 'promoted' THEN
        IF NEW.total_tests IS NULL OR NEW.total_tests < 10 THEN
            RAISE EXCEPTION
                'QA-GATE violation on expert_mutations (id=%, expert_id=%): cannot promote with total_tests=% (< 10). Mutation stays shadow until it accumulates at least 10 tests.',
                NEW.id, NEW.expert_id, NEW.total_tests;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_expert_mutations_qa_gate ON expert_mutations;

CREATE TRIGGER trg_expert_mutations_qa_gate
BEFORE INSERT OR UPDATE OF status, total_tests ON expert_mutations
FOR EACH ROW
EXECUTE FUNCTION enforce_expert_mutations_qa_gate();

COMMENT ON FUNCTION enforce_expert_mutations_qa_gate() IS
'QA-gate: forbids expert_mutations rows from being promoted (status=shadow -> promoted) with total_tests < 10. Existing already-promoted rows are exempt (transition-only check) so legacy blind promotions do not block updates.';

COMMENT ON TRIGGER trg_expert_mutations_qa_gate ON expert_mutations IS
'Enforces the statistical floor for prompt promotions: a mutation must have at least 10 shadow tests before it may be set to status=promoted. Win-rate and leaked-prompt checks are enforced in application code (promotion_engine.mutation_passes_qa_gate).';
