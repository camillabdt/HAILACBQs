PYTHON ?= $(CURDIR)/.venv/bin/python

.PHONY: backend frontend test

backend:
	cd backend && $(PYTHON) -m uvicorn haila.api:app --host 127.0.0.1 --port 8000

frontend:
	$(PYTHON) frontend/server.py --port 4173

test:
	cd backend && $(PYTHON) -m pytest -q
