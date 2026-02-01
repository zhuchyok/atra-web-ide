#!/usr/bin/env python3
"""
Импорт узлов знаний из CSV (экспорт с Mac Studio).
Использование:
  docker cp knowledge_nodes_dump.csv atra-web-ide-backend:/tmp/
  docker exec -i atra-web-ide-backend python3 -c "
import asyncio, asyncpg, csv, sys
async def run():
    conn = await asyncpg.connect('postgresql://admin:secret@knowledge_postgres:5432/knowledge_os')
    with open('/tmp/knowledge_nodes_dump.csv') as f:
        r = csv.DictReader(f)
        n = 0
        for row in r:
            try:
                await conn.execute('''
                    INSERT INTO knowledge_nodes (content, metadata, confidence_score, is_verified, usage_count, created_at)
                    VALUES (\$1, \$2, \$3, \$4, \$5, \$6)
                ''', row.get('content',''), row.get('metadata','{}'), float(row.get('confidence_score',0.5)),
                     row.get('is_verified','f')=='t', int(row.get('usage_count',0)), row.get('created_at'))
                n += 1
            except: pass
    print('Imported:', n)
asyncio.run(run())
"
"""
