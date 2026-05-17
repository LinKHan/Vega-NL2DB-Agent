"""JSON parsing helpers shared by LLM-facing modules.

Responsibilities:
- Extract strict JSON from normal model output.
- Recover the first JSON object when the model wraps it with extra text.

Used by:
- ``core.planner`` to parse planning responses.
- ``core.executor`` to parse SQL repair responses.
它负责从 LLM 输出中提取 JSON。
因为模型有时会在 JSON 外面加解释，所以这里做了容错提取。
"""

import json
import re


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("模型未返回有效的 JSON 结构")

