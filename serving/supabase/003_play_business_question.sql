-- Plays now pose the business question an alert forces (ADR 0012, revised 2026-11-26).
-- `business` stays nullable for older runs until they are cleaned up by the next publish.
alter table public.food_price_play alter column business drop not null;
alter table public.food_price_play add column question text;
alter table public.food_price_play add column exposure text check (exposure in ('cost', 'price', 'volume', 'trust'));
