from postgres import describe_table, list_schemas, list_tables, run_read_only_query
from tracing import trace


TOOLS = [
    {"type": "function", "function": {"name": "trace_action", "description": "Record a short public reason for the next action. Use before every database or semantic-generation tool; do not include private chain-of-thought.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "reason": {"type": "string"}}, "required": ["action", "reason"]}}},
    {"type": "function", "function": {"name": "list_schemas", "description": "List available PostgreSQL schemas.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_tables", "description": "List base tables in a PostgreSQL schema.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}}, "required": ["schema"]}}},
    {"type": "function", "function": {"name": "describe_table", "description": "Show columns, primary key, and foreign keys for one PostgreSQL table.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}, "table": {"type": "string"}}, "required": ["schema", "table"]}}},
    {"type": "function", "function": {"name": "run_read_only_query", "description": "Run one read-only SELECT or WITH query. Use for questions about data, counts, sums, trends, and grouped results. Results are limited to 200 rows and time out after 10 seconds.", "parameters": {"type": "object", "properties": {"sql": {"type": "string", "description": "A single PostgreSQL SELECT or WITH query."}}, "required": ["sql"]}}},
    {"type": "function", "function": {"name": "create_semantic_view", "description": "Create a semantic-view proposal for selected PostgreSQL tables.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}, "tables": {"type": "array", "items": {"type": "string"}}, "request": {"type": "string"}}, "required": ["schema", "tables", "request"]}}},
]