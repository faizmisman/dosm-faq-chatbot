run:
\tuvicorn app.main:app --reload

test:
\tpytest -q

build:
\tdocker build -t dosm-insights-api:local .
	
smoke-dev:
	python3 scripts/smoke_test.py --namespace dosm-dev --service faq-chatbot-dosm-insights --secret app-secrets --api-key-key API_KEY

