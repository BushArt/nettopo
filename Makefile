# NetTopo Makefile
# Usage: make <target>
# ─────────────────────────────────────────────────────────────────────────────

SUBNET  ?= 172.20.0.0/24
PROFILE ?= quick

.PHONY: scan test serve clean lab dev demo

## Phase 1 ────────────────────────────────────────────────────────────────────

scan:
	python main_static.py --subnet $(SUBNET) --profile $(PROFILE)

test:
	pytest tests/ -v --tb=short

serve:
	python -m http.server 8080 --directory .

clean:
	rm -rf data/sessions/*.json data/nvd_cache/*.json __pycache__ .pytest_cache

## Phase 2 (not yet implemented) ──────────────────────────────────────────────

dev:
	@echo "Phase 2: start ws_server.py + http.server with auto-reload"
	@echo "Not yet implemented — see phase/2-streaming"

lab:
	docker compose -f docker-compose.lab.yml up -d

## Phase 4 (not yet implemented) ──────────────────────────────────────────────

demo:
	python main_static.py --replay data/sessions/latest.json
