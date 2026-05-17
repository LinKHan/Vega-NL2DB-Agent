"""Compatibility entrypoint for the modular Vega NL2DB Agent.

The original V9 demo lived entirely in this file.  The code has now been
split into the ``vega_agent/`` package:

- ``config.py`` loads API/database/server settings.
- ``schema/`` owns Schema RAG metadata and formatting.
- ``db/`` owns connections, SQL safety, and read-only execution.
- ``llm/`` owns the OpenAI-compatible client and prompts.
- ``core/`` owns planning, execution, memory, and Pandas cross-db merging.
- ``render/`` owns summaries, charts, tables, and audit markdown.
- ``app_gradio.py`` builds the Gradio UI.

Keeping this thin wrapper means the old command still works:

    python baseline_3.py
"""

from vega_agent.main import main


if __name__ == "__main__":
    main()
