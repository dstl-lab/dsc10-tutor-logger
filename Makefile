.PHONY: port-forward-prod port-forward-dev push dev

port-forward-prod:
	kubectl port-forward pod/dsc10-tutor-logs-prod-0 5432:5432 -n dsc-10-llm

port-forward-dev:
	kubectl port-forward pod/dsc10-tutor-logs-dev-0 5432:5432 -n dsc-10-llm

dev:
	cd api && uv run uvicorn main:app --reload --port 8000

push:
	git add -A
	git commit -m "$$(claude -p 'write a short commit message for the staged changes. output only the message, nothing else.' 2>/dev/null)"
	git push
