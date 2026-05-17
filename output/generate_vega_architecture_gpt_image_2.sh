#!/usr/bin/env bash
set -euo pipefail

# Generates the Vega NL2DB architecture diagram with OpenAI gpt-image-2.
# Requirement: export OPENAI_API_KEY before running this script.

python /home/linkehan/.codex/skills/.system/imagegen/scripts/image_gen.py generate \
  --model gpt-image-2 \
  --prompt-file output/vega_agent_architecture_prompt.txt \
  --size 1792x1024 \
  --quality high \
  --output-format png \
  --out output/vega_agent_architecture_gpt_image_2.png \
  --force
