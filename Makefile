VERSION ?= v1
NAME ?= langgraph-api
PORT ?= 8000

docker-build:
	docker build --no-cache \
		-t $(NAME):latest \
		-t $(NAME):$(VERSION) \
		-f image/Dockerfile .

docker-stop:
	- docker rm -f $(NAME) 2>/dev/null || true
	- docker ps -q --filter "publish=$(PORT)" | xargs -r docker rm -f

docker-run: docker-build docker-stop
	docker run -d \
		-p $(PORT):8000 \
		--env-file .env \
		--name $(NAME) \
		$(NAME):$(VERSION)

docker-logs:
	docker logs -f $(NAME)

test-chat:
	curl -s -X POST http://localhost:8000/chat \
  		-H "Content-Type: application/json" \
  		-d '{"message":"Say hi"}'

test-stream:
	curl -s -N -X POST http://localhost:8000/chat/stream \
		-H "Content-Type: application/json" \
		-d '{"message":"Say hi"}'
