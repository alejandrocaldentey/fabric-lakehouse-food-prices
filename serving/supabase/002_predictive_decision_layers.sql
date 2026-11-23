-- Serving layer v2 (ADR 0009, 0010, 0011, 0012): chained indices, predictive and decision layers,
-- and platform metadata for the architecture page. Same rules as 001: CI writes with the
-- service role, everyone else can only SELECT.
--
-- Snapshot tables carry a run_id. The publisher writes the new run, marks it complete in
-- food_price_publish_log, then deletes older runs. Readers always filter on the latest complete
-- run, so they never see a half-written snapshot (a blue/green switch without transactions).

alter table public.food_price_diamond
  add column producer_price_index double precision,
  add column consumer_food_price_index double precision;

alter table public.food_price_publish_log
  add column run_id text,
  add column status text not null default 'complete' check (status in ('running', 'complete')),
  add column stats jsonb;

-- chain-linked indices, kept for the "trace a number" view (ADR 0010)
create table public.food_price_index (
  country_iso3 text not null references public.food_price_country (country_iso3),
  series_code text not null check (series_code in ('PRODUCER_PI', 'CONSUMER_FOOD_PI')),
  year int not null,
  index_value double precision not null,
  source_unit text not null,
  source_value double precision not null,
  rebase_factor double precision not null,
  link_year int,
  primary key (country_iso3, series_code, year)
);

create table public.food_price_model (
  run_id text not null,
  model_id text not null,
  label text not null,
  family text not null,
  formula text not null,
  how_it_works text not null,
  strengths text not null,
  weaknesses text not null,
  when_to_use text not null,
  is_champion boolean not null,
  n_backtest int not null,
  mae double precision not null,
  rmse double precision not null,
  bias double precision not null,
  skill_vs_naive double precision,
  mae_shock_years double precision,
  mae_recent double precision,
  trained_through int not null,
  sort_order int not null,
  primary key (run_id, model_id)
);

create table public.food_price_backtest (
  run_id text not null,
  model_id text not null,
  country_iso3 text not null,
  year int not null,
  actual double precision not null,
  predicted double precision not null,
  primary key (run_id, model_id, country_iso3, year)
);

create table public.food_price_forecast (
  run_id text not null,
  model_id text not null,
  country_iso3 text not null,
  target_year int not null,
  predicted double precision not null,
  lower_80 double precision not null,
  upper_80 double precision not null,
  is_champion boolean not null,
  input_consumer_yoy double precision not null,
  input_producer_yoy double precision not null,
  input_producer_yoy_lag1 double precision not null,
  primary key (run_id, model_id, country_iso3, target_year)
);

create table public.food_price_model_coef (
  run_id text not null,
  model_id text not null,
  kind text not null check (kind in ('slope', 'intercept')),
  country_iso3 text not null default '',
  term text not null,
  value double precision not null,
  primary key (run_id, model_id, kind, country_iso3, term)
);

create table public.food_price_alert_rule (
  run_id text not null,
  rule_id text not null,
  label text not null,
  category text not null,
  scope text not null,
  value_expression text not null,
  unit text not null,
  levels jsonb not null,
  message text not null,
  sort_order int not null,
  primary key (run_id, rule_id)
);

create table public.food_price_alert (
  run_id text not null,
  alert_id text not null,
  rule_id text not null,
  category text not null,
  country_iso3 text,
  year int not null,
  severity text not null check (severity in ('high', 'medium')),
  value double precision not null,
  primary key (run_id, alert_id)
);

create table public.food_price_role (
  run_id text not null,
  role_id text not null,
  label text not null,
  focus text not null,
  sort_order int not null,
  primary key (run_id, role_id)
);

create table public.food_price_play (
  run_id text not null,
  rule_id text not null,
  role_id text not null,
  business text not null,
  data text not null,
  kpi text not null,
  horizon text not null,
  primary key (run_id, rule_id, role_id)
);

-- platform metadata (lineage, contracts, product descriptor, run statistics) as JSON documents
create table public.food_price_artifact (
  run_id text not null,
  name text not null,
  body jsonb not null,
  primary key (run_id, name)
);

do $$
declare t text;
begin
  foreach t in array array['food_price_index', 'food_price_model', 'food_price_backtest',
    'food_price_forecast', 'food_price_model_coef', 'food_price_alert_rule', 'food_price_alert',
    'food_price_role', 'food_price_play', 'food_price_artifact']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "public read" on public.%I for select to anon, authenticated using (true)', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select on public.%I to anon, authenticated', t);
    execute format('grant all on public.%I to service_role', t);
  end loop;
end $$;

create index on public.food_price_backtest (run_id, country_iso3);
create index on public.food_price_alert (run_id, country_iso3);
