-- [v149.54] defense-in-depth для task_status_audit:
-- если инфраструктурная подпись (application_name сквозь pgbouncer) пуста/мусорна,
-- триггер достраивает подпись из контекста задачи (processing_worker/completed_by),
-- последний резерв — адрес клиента с маркером unidentified.
CREATE OR REPLACE FUNCTION fn_task_status_audit() RETURNS trigger AS $fn$
BEGIN
  IF NEW.status <> OLD.status THEN
    DECLARE
      v_app text := NULLIF(current_setting('application_name', true), '');
    BEGIN
      IF v_app IS NULL OR v_app IN ('unknown', 'pgbouncer_backend') THEN
        v_app := COALESCE(
          NULLIF(NEW.metadata->>'processing_worker', ''),
          NULLIF(NEW.metadata->>'completed_by', ''),
          'unidentified@' || COALESCE(inet_client_addr()::text, 'unix')
        );
      END IF;
      INSERT INTO task_status_audit (task_id, old_status, new_status, app_name, client_addr, backend_pid, query_text)
      VALUES (NEW.id, OLD.status, NEW.status,
              v_app,
              COALESCE(inet_client_addr()::text, 'unix'),
              pg_backend_pid(), left(current_query(), 400));
    END;
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;
