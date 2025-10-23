.PHONY: help build up down logs test-unit test-integration test-all clean

help:
	@echo "📋 Available commands:"
	@echo "  make build              - Build all Docker containers"
	@echo "  make up                 - Start all services"
	@echo "  make down               - Stop all services"
	@echo "  make logs               - Follow logs from all services"
	@echo "  make test-unit          - Run unit tests"
	@echo "  make test-integration   - Run integration tests"
	@echo "  make test-all           - Run all tests"
	@echo "  make clean              - Clean up containers and volumes"

build:
	@echo "🔨 Building Docker containers..."
	docker-compose build

up:
	@echo "🚀 Starting services..."
	docker-compose up -d
	@echo "✅ Services started!"
	@echo "   - noVNC viewer: http://localhost:6080/vnc.html"
	@echo "   - API: http://localhost:8000 (when enabled)"

down:
	@echo "🛑 Stopping services..."
	docker-compose down

logs:
	@echo "📄 Following logs..."
	docker-compose logs -f

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/ -v -k "not integration" --tb=short

test-integration:
	@echo "🔗 Running integration tests..."
	@bash scripts/validate_stack.sh

test-all: test-unit test-integration
	@echo "✅ All tests completed!"

clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	rm -rf data/*.db
	@echo "✅ Cleanup complete!"

