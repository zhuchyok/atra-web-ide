#!/usr/bin/env python3
"""Batch insert all curator standard files into knowledge_nodes."""

import os
import uuid
import json
import psycopg2
from datetime import datetime
import psycopg2.extras
psycopg2.extras.register_uuid()

STANDARDS_DIR = "/Users/bikos/Documents/atra-web-ide/docs/curator_reports/standards"
DOMAIN_ID = "590db00e-6337-410f-933b-bf1ae83ec54c"
ALREADY_INSERTED = {"problem_solving.md"}  # already deployed via earlier script

conn = psycopg2.connect(
    dbname="knowledge_os",
    user="admin",
    password="secret",
    host="localhost",
    port=6432,
)
cur = conn.cursor()

files = sorted(os.listdir(STANDARDS_DIR))
inserted = 0

for fname in files:
    if not fname.endswith(".md"):
        continue
    if fname in ALREADY_INSERTED:
        print(f"SKIP {fname} (already inserted)")
        continue
    fpath = os.path.join(STANDARDS_DIR, fname)
    with open(fpath) as f:
        content = f.read()

    standard_name = fname.replace(".md", "")

    cur.execute("""
        INSERT INTO knowledge_nodes
            (id, content, metadata, confidence_score, is_verified, domain_id, source_ref, created_at)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (
        str(uuid.uuid4()),
        content,
        json.dumps({"source": "curator", "type": "standard", "expert": "curator", "project_slug": "atra-web-ide"}),
        0.95,
        True,
        DOMAIN_ID,
        fname,
        datetime.utcnow(),
    ))
    inserted += 1
    print(f"INSERT {fname}")

conn.commit()
cur.close()
conn.close()
print(f"\nDone. Inserted {inserted} new standards into knowledge_nodes.")
