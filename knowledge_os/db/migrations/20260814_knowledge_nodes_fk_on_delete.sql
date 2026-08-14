-- v136: allow knowledge_nodes prune without FK storms on expert_discussions/tasks.
-- World practice: SET NULL on optional references; CASCADE already on knowledge_edges.

ALTER TABLE expert_discussions
    DROP CONSTRAINT IF EXISTS expert_discussions_knowledge_node_id_fkey;

ALTER TABLE expert_discussions
    ADD CONSTRAINT expert_discussions_knowledge_node_id_fkey
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
    ON DELETE SET NULL;

ALTER TABLE tasks
    DROP CONSTRAINT IF EXISTS tasks_knowledge_node_id_fkey;

ALTER TABLE tasks
    ADD CONSTRAINT tasks_knowledge_node_id_fkey
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
    ON DELETE SET NULL;
