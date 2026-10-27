# Unclaimed — task shortcuts. Windows users: the same commands exist as scripts/*.ps1.
PY ?= python

.PHONY: install data compile test eval build demo dev up

install:
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm install

data:
	cd backend && $(PY) -m unclaimed.datagen

compile:
	cd backend && $(PY) -m unclaimed.compiler

test:
	cd backend && $(PY) -m pytest -q

eval:
	$(PY) eval/run.py

build:
	cd frontend && npm run build

# Demo: replay cache only (no API calls), reset memory + seed demo rule pack, serve UI on :8000
demo: build
	$(PY) scripts/demo.py

dev:
	cd backend && $(PY) -m uvicorn unclaimed.api:app --reload --port 8000

up:
	docker compose up --build
