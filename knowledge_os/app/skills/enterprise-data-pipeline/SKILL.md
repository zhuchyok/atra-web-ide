---
name: enterprise-data-pipeline
description: Enterprise data pipeline automation. Retrieval skills для работы с данными - извлечение, трансформация и загрузка в enterprise системы.
---

# Enterprise Data Pipeline Skill

## Когда использовать

- ETL процессы для enterprise данных
- Data retrieval из enterprise систем
- Data transformation и cleaning
- Integration с enterprise platforms (Salesforce, SAP, etc)

## Retrieval Skills Pipeline

### 1. Data Discovery

Определи источники данных:

- CRM (Salesforce, HubSpot)
- ERP (SAP, Oracle)
- Data Warehouse (Snowflake, BigQuery)
- APIs (REST, GraphQL)

### 2. Data Extraction

```python
# Example extraction patterns
async def extract_from_salesforce():
    """Salesforce data extraction"""
    query = "SELECT Id, Name, Email FROM Lead"
    results = await sf.query(query)
    return transform(results)

async def extract_from_snowflake():
    """Snowflake data extraction"""
    query = "SELECT * FROM table WHERE date > last_run"
    return await snowflake.query(query)
```

### 3. Data Transformation

```python
def transform(raw_data):
    # Clean
    data = clean_nulls(raw_data)

    # Normalize
    data = normalize_dates(data)
    data = normalize_types(data)

    # Enrich
    data = add_computed_fields(data)

    return data
```

### 4. Data Loading

```python
async def load_to_destination(data, destination):
    if destination == 'snowflake':
        await load_to_snowflake(data)
    elif destination == 'bigquery':
        await load_to_bigquery(data)
    elif destination == 'api':
        await push_to_api(data)
```

## Enterprise Integration Patterns

### API Rate Limiting

```python
async def api_call_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = await make_request(url)
            if response.status == 200:
                return response
            elif response.status == 429:
                wait(rate_limit_timeout)
                continue
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(exponential_backoff(attempt))
```

### Batch Processing

```python
async def batch_process(items, batch_size=100):
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        batch_results = await process_batch(batch)
        results.extend(batch_results)
        await asyncio.sleep(1)  # Rate limiting
    return results
```

### Error Handling

```python
async def safe_pipeline(data):
    try:
        result = await pipeline(data)
        log.success(f"Processed {len(data)} records")
    except ValidationError as e:
        log.error(f"Validation failed: {e}")
        await alert_team(f"Validation error: {e}")
    except APILimitError as e:
        log.warning(f"Rate limited, retrying...")
        await asyncio.sleep(backoff)
        result = await retry_pipeline(data)
    except Exception as e:
        log.critical(f"Pipeline failed: {e}")
        await notify_oncall(f"Pipeline down: {e}")
    finally:
        await cleanup()
```

## Output Formats

- **JSON** - structured data
- **Parquet** - analytical queries
- **CSV** - exports
- **DataFrame** - pandas

## Monitoring

```python
# Track metrics
metrics = {
    'records_processed': len(data),
    'records_failed': failures,
    'duration_seconds': elapsed,
    'success_rate': success / total
}
await metrics_client.send(metrics)
```
