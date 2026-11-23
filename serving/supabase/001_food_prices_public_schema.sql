-- Public, read-only serving layer for the food-price-transmission data product (ADR 0008).
-- Applied to the Supabase project `portfolio-public-demo`.
-- Written only by the CI publisher (service role); read by anyone through RLS select policies.

create table public.food_price_country (
  country_iso3 text primary key,
  country_name text not null
);

create table public.food_price_metric (
  name text primary key,
  label text not null,
  description text not null,
  unit text not null,
  status text not null check (status in ('certified', 'experimental', 'deprecated')),
  owner text not null,
  sort_order int not null
);

create table public.food_price_diamond (
  country_iso3 text not null references public.food_price_country (country_iso3),
  year int not null check (year between 2000 and 2100),
  producer_price_change_pct double precision,
  consumer_food_price_change_pct double precision,
  food_price_gap_pp double precision,
  pass_through_ratio_lag1 double precision,
  headline_inflation_pct double precision,
  food_inflation_premium_pp double precision,
  primary key (country_iso3, year)
);

create table public.food_price_publish_log (
  id bigint generated always as identity primary key,
  published_at timestamptz not null default now(),
  git_sha text,
  rows_diamond int not null,
  source_note text
);

alter table public.food_price_country enable row level security;
alter table public.food_price_metric enable row level security;
alter table public.food_price_diamond enable row level security;
alter table public.food_price_publish_log enable row level security;

create policy "public read" on public.food_price_country for select to anon, authenticated using (true);
create policy "public read" on public.food_price_metric for select to anon, authenticated using (true);
create policy "public read" on public.food_price_diamond for select to anon, authenticated using (true);
create policy "public read" on public.food_price_publish_log for select to anon, authenticated using (true);

revoke all on public.food_price_country, public.food_price_metric, public.food_price_diamond, public.food_price_publish_log from anon, authenticated;
grant select on public.food_price_country, public.food_price_metric, public.food_price_diamond, public.food_price_publish_log to anon, authenticated;
grant all on public.food_price_country, public.food_price_metric, public.food_price_diamond, public.food_price_publish_log to service_role;
