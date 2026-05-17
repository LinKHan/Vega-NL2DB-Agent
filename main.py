"""Root compatibility entrypoint.

This file keeps startup simple for demos:

    python main.py

It delegates all real work to ``vega_agent.main``.
"""

from vega_agent.main import main


if __name__ == "__main__":
    main()
