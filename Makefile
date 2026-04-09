.PHONY: up down logs test lint seed restart clean

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest

lint:
	docker compose exec backend ruff check .

seed:
	docker compose exec backend python -m app.seed

restart: down up

clean:
	docker compose down -v
