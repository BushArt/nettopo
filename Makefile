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
	@echo ""
	@echo "  Open: http://localhost:8080/frontend/index.html"
	@echo ""
	python -m http.server 8080 --directory .

clean:
	rm -rf data/sessions/*.json data/nvd_cache/*.json __pycache__ .pytest_cache

## Phase 2 (not yet implemented) ──────────────────────────────────────────────

dev:
	@echo ""
	@echo "  WebSocket: ws://localhost:8765"
	@echo "  HTTP:      http://localhost:8080/frontend/index.html"
	@echo ""
	python main.py

lab:
	docker compose -f docker-compose.lab.yml up -d

## Phase 4 (not yet implemented) ──────────────────────────────────────────────

demo:
	python main_static.py --replay data/sessions/latest.json
