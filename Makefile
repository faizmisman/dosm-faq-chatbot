run:
\tuvicorn app.main:app --reload

test:
\tpytest -q

build:
\tdocker build -t dosm-insights-api:local .
