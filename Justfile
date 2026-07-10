# Resolution Cache task runner.

emulator_host := "localhost:9010"

sync:
    uv sync

lint:
    uv run ruff check src tests
    uv run ruff format --check src tests

test:
    SPANNER_EMULATOR_HOST={{emulator_host}} uv run pytest -q

test-unit:
    uv run pytest -q

emulator:
    docker rm -f spanner-emulator 2>/dev/null || true
    docker run -d --name spanner-emulator -p 9010:9010 -p 9020:9020 \
        gcr.io/cloud-spanner-emulator/emulator
    sleep 3

emulator-stop:
    docker rm -f spanner-emulator 2>/dev/null || true
