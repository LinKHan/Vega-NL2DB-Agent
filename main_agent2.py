"""Root compatibility entrypoint for the embedding Schema RAG variant.

Run:
    python main_agent2.py

The original keyword/rule Schema RAG version remains available through
``main.py`` or ``baseline_3.py``.
"""

from vega_agent2.main import main


if __name__ == "__main__":
    main()

