.PHONY: install demo serve record

install:
	uv sync

demo:
	uv run mcpgauge run examples/poisoning.yaml

serve:
	uv run mcpgauge serve

record:
	bash record_demo.sh
