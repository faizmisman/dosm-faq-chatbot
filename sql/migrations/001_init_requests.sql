create table if not exists inference_requests (
  id serial primary key,
  request_id uuid not null,
  created_at timestamptz default now(),
  user_id text,
  query text,
  answer text,
  model_version text,
  latency_ms integer,
  is_refusal boolean,
  is_low_confidence boolean
);
