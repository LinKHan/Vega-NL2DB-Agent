"""Application entrypoint for the modular Vega NL2DB Agent.

Responsibilities:
- Build the Gradio app from ``app_gradio``.
- Apply server host/port configuration.
- Launch the web application.

Used by:
- ``python -m vega_agent.main``
- The root-level compatibility ``main.py`` and ``baseline_3.py`` wrappers.
"""

from vega_agent.app_gradio import build_demo
from vega_agent.config import GRADIO_SERVER_NAME, GRADIO_SERVER_PORT


def main():
    demo = build_demo()
    launch_kwargs = {"server_name": GRADIO_SERVER_NAME}
    if GRADIO_SERVER_PORT:
        launch_kwargs["server_port"] = int(GRADIO_SERVER_PORT)
    demo.launch(**launch_kwargs)


if __name__ == "__main__":
    main()

