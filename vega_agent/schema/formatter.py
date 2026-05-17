"""Prompt formatting for retrieved schema.

Responsibilities:
- Convert schema catalog entries into compact, readable prompt snippets.

Used by:
- ``core.planner`` for planning prompts.
- ``core.executor`` for SQL repair prompts.
"""


def format_schema_for_prompt(schema_items: list) -> str:
    chunks = []
    for item in schema_items:
        col_lines = "\n".join([f"- {name} ({dtype}): {desc}" for name, dtype, desc in item["columns"]])
        table_name = f'"{item["table"]}"' if item["table"] in {"user", "order"} else item["table"]
        chunks.append(
            f"数据库: {item['db']}\n"
            f"表名: {table_name}\n"
            f"含义: {item['description']}\n"
            f"字段:\n{col_lines}"
        )
    return "\n\n".join(chunks)
