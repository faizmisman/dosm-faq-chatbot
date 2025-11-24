run:
\tuvicorn app.main:app --reload

test:
\tpytest -q

build:
	docker build -t dosm-insights-api:local .

build-airflow:
	docker build -f deploy/airflow.Dockerfile -t dosmfaqchatbotacr1lw5a.azurecr.io/airflow:latest .

push-airflow:
	az acr login --name dosmfaqchatbotacr1lw5a
	docker push dosmfaqchatbotacr1lw5a.azurecr.io/airflow:latest
	
smoke-dev:
	python3 scripts/smoke_test.py --namespace dosm-dev --service faq-chatbot-dosm-insights --secret app-secrets --api-key-key API_KEY

