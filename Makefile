.PHONY: up down logs test lint seed

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest && docker compose exec frontend npm test

lint:
	docker compose exec backend ruff check . && docker compose exec frontend npm run lint

seed:
	docker compose exec backend python -m app.seed
