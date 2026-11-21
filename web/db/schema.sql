-- Inventario de hardware del equipo CRBRC (Platanus Hack 26).
-- Base: Neon, proyecto "crbrc-platanus", base "inventario".
-- Correr con: psql "$DATABASE_URL" -f db/schema.sql  (es idempotente)

create extension if not exists unaccent;

create table if not exists items (
  id              serial primary key,
  nombre          text not null,                 -- "Ítem" en el Sheet original
  cantidad        integer,                       -- "Cant."; null = no se sabe
  categoria       text not null default 'Otros',
  origen          text,                          -- de quién es o de dónde salió
  estado          text not null default 'Listo', -- Listo, Por verificar, Sin identificar, En uso, Dañado, Prestado
  uso_bicho       text,                          -- para qué sirve en el robot
  ubicacion       text,                          -- dónde está físicamente
  notas           text,
  uso_lampara     text,                          -- columna de la idea anterior (lámpara); se conserva
  fuente          text,                          -- pestaña del Sheet de donde vino
  creado          timestamptz not null default now(),
  actualizado     timestamptz not null default now(),
  actualizado_por text
);

create table if not exists cambios (
  id       bigserial primary key,
  item_id  integer,
  accion   text not null check (accion in ('crear','editar','borrar')),
  antes    jsonb,
  despues  jsonb,
  autor    text,
  fecha    timestamptz not null default now()
);

create index if not exists cambios_fecha_idx on cambios (fecha desc);
create index if not exists cambios_item_idx on cambios (item_id);
