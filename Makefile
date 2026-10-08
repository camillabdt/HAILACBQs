PYTHON ?= $(CURDIR)/.venv/bin/python

.PHONY: backend frontend test verify-slm

backend:
	@set -a; [ ! -f .env ] || . ./.env; set +a; \
	cd backend && $(PYTHON) -m uvicorn haila.api:app --host 127.0.0.1 --port 8000

frontend:
	@set -a; [ ! -f .env ] || . ./.env; set +a; \
	$(PYTHON) frontend/server.py --port 4173

test:
	cd backend && $(PYTHON) -m pytest -q

verify-slm:
	@set -a; [ ! -f .env ] || . ./.env; set +a; \
	$(PYTHON) scripts/verificar_slm.py
