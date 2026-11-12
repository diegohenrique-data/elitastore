-- =====================================================================
-- Projeto Elita: estrutura inicial do banco de dados
-- Baseado na "Versão Simples" (revisão 3), seção 4.
--
-- Regras de segurança:
-- - RLS ligado em TODAS as tabelas.
-- - Só quem tem perfil ATIVO (Elita ou ajudante) acessa os dados.
-- - Só a DONA apaga, vê custo dos produtos, gastos e configura a loja.
-- - Cada pagamento é uma linha separada. O "quanto falta" é calculado
--   (views), nunca guardado pronto.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Schema privado (não aparece na API) para as funções de permissão
-- ---------------------------------------------------------------------
create schema if not exists privado;
revoke all on schema privado from public, anon;
grant usage on schema privado to authenticated;

-- ---------------------------------------------------------------------
-- PERFIS: quem entra no sistema (Elita = dona, ajudante)
-- ---------------------------------------------------------------------
create table public.perfis (
  id uuid primary key references auth.users (id) on delete cascade,
  nome text not null default '',
  papel text not null default 'ajudante' check (papel in ('dona', 'ajudante')),
  ativo boolean not null default false,
  criado_em timestamptz not null default now()
);

create or replace function privado.sou_membro()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.perfis
    where id = (select auth.uid()) and ativo
  );
$$;

create or replace function privado.sou_dona()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.perfis
    where id = (select auth.uid()) and ativo and papel = 'dona'
  );
$$;

revoke all on function privado.sou_membro() from public, anon;
revoke all on function privado.sou_dona() from public, anon;
grant execute on function privado.sou_membro() to authenticated;
grant execute on function privado.sou_dona() to authenticated;

-- A primeira pessoa a se cadastrar vira a DONA (a Elita).
-- As próximas ficam como ajudante DESATIVADA até a Elita liberar.
create or replace function privado.criar_perfil()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if exists (select 1 from public.perfis) then
    insert into public.perfis (id, nome, papel, ativo)
    values (new.id, coalesce(new.raw_user_meta_data ->> 'nome', ''), 'ajudante', false);
  else
    insert into public.perfis (id, nome, papel, ativo)
    values (new.id, coalesce(new.raw_user_meta_data ->> 'nome', 'Elita'), 'dona', true);
  end if;
  return new;
end;
$$;

revoke all on function privado.criar_perfil() from public, anon, authenticated;

create trigger ao_criar_usuario
  after insert on auth.users
  for each row execute function privado.criar_perfil();

-- ---------------------------------------------------------------------
-- CONFIGURAÇÕES da loja (uma linha só)
-- ---------------------------------------------------------------------
create table public.configuracoes (
  id smallint primary key default 1 check (id = 1),
  nome_loja text not null default 'Loja da Elita',
  chave_pix text not null default '',
  msg_cobranca text not null default 'Oi {nome}, tudo bem? Passando para lembrar da parcela de {valor}. Meu Pix é {pix}. Obrigada! 😊',
  msg_encomenda text not null default 'Oi {nome}, sua encomenda chegou! 😊',
  dias_parado integer not null default 60 check (dias_parado > 0),
  dias_aviso_validade integer not null default 30 check (dias_aviso_validade > 0),
  estoque_minimo_padrao integer not null default 3 check (estoque_minimo_padrao >= 0)
);
insert into public.configuracoes (id) values (1);

-- ---------------------------------------------------------------------
-- CLIENTES (pessoas)
-- ---------------------------------------------------------------------
create table public.clientes (
  id uuid primary key default gen_random_uuid(),
  nome text not null check (length(trim(nome)) > 0),
  whatsapp text not null default '',
  endereco text not null default '',
  observacoes text not null default '',
  criado_em timestamptz not null default now(),
  criado_por uuid default auth.uid() references public.perfis (id) on delete set null
);
create index clientes_nome_idx on public.clientes (lower(nome));

-- ---------------------------------------------------------------------
-- CATEGORIAS e subcategorias (livres)
-- ---------------------------------------------------------------------
create table public.categorias (
  id uuid primary key default gen_random_uuid(),
  nome text not null check (length(trim(nome)) > 0),
  categoria_pai_id uuid references public.categorias (id) on delete restrict,
  tipo text not null default 'produto' check (tipo in ('produto', 'servico')),
  criado_em timestamptz not null default now()
);
create index categorias_pai_idx on public.categorias (categoria_pai_id);

-- ---------------------------------------------------------------------
-- FORNECEDORES (só a agenda)
-- ---------------------------------------------------------------------
create table public.fornecedores (
  id uuid primary key default gen_random_uuid(),
  nome text not null check (length(trim(nome)) > 0),
  whatsapp text not null default '',
  cidade text not null default '',
  o_que_vende text not null default '',
  criado_em timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- PRODUTOS e serviços
-- ---------------------------------------------------------------------
create table public.produtos (
  id uuid primary key default gen_random_uuid(),
  nome text not null check (length(trim(nome)) > 0),
  categoria_id uuid references public.categorias (id) on delete set null,
  fornecedor_id uuid references public.fornecedores (id) on delete set null,
  codigo_barras text unique,
  preco numeric(10, 2) not null default 0 check (preco >= 0),
  quantidade integer not null default 0 check (quantidade >= 0),
  estoque_minimo integer check (estoque_minimo >= 0),
  validade date,
  entrou_em date not null default (now() at time zone 'America/Sao_Paulo')::date,
  ativo boolean not null default true,
  criado_em timestamptz not null default now()
);
create index produtos_categoria_idx on public.produtos (categoria_id);
create index produtos_fornecedor_idx on public.produtos (fornecedor_id);

-- Custo fica numa tabela separada: a ajudante NÃO pode ver.
create table public.produtos_custo (
  produto_id uuid primary key references public.produtos (id) on delete cascade,
  preco_custo numeric(10, 2) not null default 0 check (preco_custo >= 0)
);

-- Até 3 fotos por produto (a 1ª é a principal). O arquivo fica no Storage (bucket "fotos").
create table public.produto_fotos (
  id uuid primary key default gen_random_uuid(),
  produto_id uuid not null references public.produtos (id) on delete cascade,
  caminho text not null,
  ordem smallint not null default 1 check (ordem between 1 and 3),
  criado_em timestamptz not null default now(),
  unique (produto_id, ordem)
);

-- ---------------------------------------------------------------------
-- VENDAS
-- ---------------------------------------------------------------------
create table public.vendas (
  id uuid primary key default gen_random_uuid(),
  cliente_id uuid references public.clientes (id) on delete restrict, -- vazio = balcão
  vendida_em timestamptz not null default now(),
  forma_pagamento text not null check (forma_pagamento in ('dinheiro', 'pix', 'cartao', 'fiado')),
  total numeric(10, 2) not null check (total >= 0),
  vezes smallint check (vezes between 1 and 24),
  dia_pagamento smallint check (dia_pagamento between 1 and 31),
  observacao text not null default '',
  vendido_por uuid default auth.uid() references public.perfis (id) on delete set null,
  -- Regra 1: fiado só com o cadastro da pessoa
  constraint fiado_precisa_cliente check (forma_pagamento <> 'fiado' or cliente_id is not null),
  constraint fiado_precisa_vezes check (forma_pagamento <> 'fiado' or (vezes is not null and dia_pagamento is not null))
);
create index vendas_cliente_idx on public.vendas (cliente_id);
create index vendas_data_idx on public.vendas (vendida_em);

create table public.venda_itens (
  id uuid primary key default gen_random_uuid(),
  venda_id uuid not null references public.vendas (id) on delete cascade,
  produto_id uuid references public.produtos (id) on delete set null,
  descricao text not null,
  quantidade integer not null default 1 check (quantidade > 0),
  preco_unitario numeric(10, 2) not null check (preco_unitario >= 0)
);
create index venda_itens_venda_idx on public.venda_itens (venda_id);
create index venda_itens_produto_idx on public.venda_itens (produto_id);

-- Vendeu, saiu do estoque (regra 8).
create or replace function public.baixar_estoque()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new.produto_id is not null then
    update public.produtos
      set quantidade = greatest(0, quantidade - new.quantidade)
      where id = new.produto_id;
  end if;
  return new;
end;
$$;
revoke all on function public.baixar_estoque() from public, anon;

create trigger ao_vender_item
  after insert on public.venda_itens
  for each row execute function public.baixar_estoque();

-- ---------------------------------------------------------------------
-- FIADO: parcelas, pagamentos e ajustes
-- ---------------------------------------------------------------------
create table public.parcelas (
  id uuid primary key default gen_random_uuid(),
  venda_id uuid references public.vendas (id) on delete cascade,
  cliente_id uuid not null references public.clientes (id) on delete restrict,
  numero smallint not null default 1,
  valor numeric(10, 2) not null check (valor >= 0),
  vencimento date not null,
  observacao text not null default '', -- ex.: "do caderno antigo"
  criado_em timestamptz not null default now()
);
create index parcelas_cliente_idx on public.parcelas (cliente_id, vencimento);
create index parcelas_venda_idx on public.parcelas (venda_id);

-- Cada pagamento é uma linha. Paga menos: o que falta continua. Paga mais: abate da próxima.
create table public.pagamentos (
  id uuid primary key default gen_random_uuid(),
  cliente_id uuid not null references public.clientes (id) on delete restrict,
  valor numeric(10, 2) not null check (valor > 0),
  forma text not null check (forma in ('dinheiro', 'pix', 'cartao')),
  pago_em date not null default (now() at time zone 'America/Sao_Paulo')::date,
  observacao text not null default '',
  anotado_por uuid default auth.uid() references public.perfis (id) on delete set null,
  criado_em timestamptz not null default now()
);
create index pagamentos_cliente_idx on public.pagamentos (cliente_id);
create index pagamentos_data_idx on public.pagamentos (pago_em);

-- Histórico de "AJUSTAR VALOR" e "MUDAR DATA" (antes, depois, quando, quem).
create table public.ajustes (
  id uuid primary key default gen_random_uuid(),
  cliente_id uuid not null references public.clientes (id) on delete cascade,
  parcela_id uuid references public.parcelas (id) on delete set null,
  tipo text not null check (tipo in ('valor', 'data', 'vezes')),
  antes text not null,
  depois text not null,
  motivo text not null default '',
  feito_por uuid default auth.uid() references public.perfis (id) on delete set null,
  feito_em timestamptz not null default now()
);
create index ajustes_cliente_idx on public.ajustes (cliente_id);
create index ajustes_parcela_idx on public.ajustes (parcela_id);

-- ---------------------------------------------------------------------
-- ENCOMENDAS
-- ---------------------------------------------------------------------
create table public.encomendas (
  id uuid primary key default gen_random_uuid(),
  cliente_id uuid not null references public.clientes (id) on delete restrict,
  descricao text not null check (length(trim(descricao)) > 0),
  foto_caminho text,
  fornecedor_id uuid references public.fornecedores (id) on delete set null,
  preco numeric(10, 2) check (preco >= 0),
  sinal numeric(10, 2) not null default 0 check (sinal >= 0),
  etapa text not null default 'pedido' check (etapa in ('pedido', 'chegou', 'entregue')),
  venda_id uuid references public.vendas (id) on delete set null,
  criado_em timestamptz not null default now(),
  chegou_em timestamptz,
  entregue_em timestamptz
);
create index encomendas_cliente_idx on public.encomendas (cliente_id);
create index encomendas_fornecedor_idx on public.encomendas (fornecedor_id);
create index encomendas_venda_idx on public.encomendas (venda_id);
create index encomendas_etapa_idx on public.encomendas (etapa);

-- ---------------------------------------------------------------------
-- GASTOS (só a Elita)
-- ---------------------------------------------------------------------
create table public.gastos (
  id uuid primary key default gen_random_uuid(),
  gasto_em date not null default (now() at time zone 'America/Sao_Paulo')::date,
  valor numeric(10, 2) not null check (valor > 0),
  descricao text not null check (length(trim(descricao)) > 0),
  criado_por uuid default auth.uid() references public.perfis (id) on delete set null,
  criado_em timestamptz not null default now()
);
create index gastos_data_idx on public.gastos (gasto_em);

-- índices das chaves estrangeiras de "quem fez"
create index clientes_criado_por_idx on public.clientes (criado_por);
create index vendas_vendido_por_idx on public.vendas (vendido_por);
create index pagamentos_anotado_por_idx on public.pagamentos (anotado_por);
create index ajustes_feito_por_idx on public.ajustes (feito_por);
create index gastos_criado_por_idx on public.gastos (criado_por);

-- =====================================================================
-- VIEWS (cálculos). security_invoker = respeitam o RLS de quem consulta.
-- =====================================================================

-- Situação de cada parcela: o pagamento abate das parcelas mais antigas primeiro.
create view public.parcelas_situacao
with (security_invoker = true)
as
with ordenadas as (
  select
    p.*,
    coalesce(sum(p.valor) over (
      partition by p.cliente_id
      order by p.vencimento, p.numero, p.criado_em, p.id
      rows between unbounded preceding and 1 preceding
    ), 0) as acumulado_antes
  from public.parcelas p
),
pagos as (
  select cliente_id, sum(valor) as total_pago
  from public.pagamentos
  group by cliente_id
),
calculo as (
  select
    o.*,
    least(o.valor, greatest(0, coalesce(pg.total_pago, 0) - o.acumulado_antes)) as pago
  from ordenadas o
  left join pagos pg on pg.cliente_id = o.cliente_id
)
select
  c.id,
  c.venda_id,
  c.cliente_id,
  c.numero,
  c.valor,
  c.vencimento,
  c.observacao,
  c.pago,
  c.valor - c.pago as falta,
  case
    when c.valor - c.pago <= 0 then 'paga'
    when c.vencimento < (now() at time zone 'America/Sao_Paulo')::date then 'atrasada'
    when c.vencimento = (now() at time zone 'America/Sao_Paulo')::date then 'hoje'
    else 'proxima'
  end as situacao
from calculo c;

-- Quanto cada pessoa deve (FIADO: me devem).
create view public.clientes_saldo
with (security_invoker = true)
as
select
  cl.id as cliente_id,
  cl.nome,
  cl.whatsapp,
  coalesce(sum(ps.falta), 0) as falta_total,
  coalesce(sum(ps.falta) filter (where ps.situacao = 'atrasada'), 0) as atrasado,
  coalesce(sum(ps.falta) filter (where ps.situacao = 'hoje'), 0) as hoje,
  min(ps.vencimento) filter (where ps.situacao <> 'paga') as proximo_vencimento
from public.clientes cl
left join public.parcelas_situacao ps on ps.cliente_id = cl.id
group by cl.id, cl.nome, cl.whatsapp;

-- =====================================================================
-- PERMISSÕES (RLS)
-- =====================================================================
alter table public.perfis enable row level security;
alter table public.configuracoes enable row level security;
alter table public.clientes enable row level security;
alter table public.categorias enable row level security;
alter table public.fornecedores enable row level security;
alter table public.produtos enable row level security;
alter table public.produtos_custo enable row level security;
alter table public.produto_fotos enable row level security;
alter table public.vendas enable row level security;
alter table public.venda_itens enable row level security;
alter table public.parcelas enable row level security;
alter table public.pagamentos enable row level security;
alter table public.ajustes enable row level security;
alter table public.encomendas enable row level security;
alter table public.gastos enable row level security;

-- Ninguém sem login acessa nada.
revoke all on all tables in schema public from anon;
grant select, insert, update, delete on all tables in schema public to authenticated;

-- PERFIS: cada um vê o próprio; a dona vê e altera todos (liberar/tirar ajudante).
create policy "perfis: ver o proprio ou dona ve todos" on public.perfis
  for select to authenticated
  using (id = (select auth.uid()) or (select privado.sou_dona()));
create policy "perfis: dona altera" on public.perfis
  for update to authenticated
  using ((select privado.sou_dona()))
  with check ((select privado.sou_dona()));

-- CONFIGURAÇÕES: todos leem; só a dona muda.
create policy "configuracoes: membros leem" on public.configuracoes
  for select to authenticated using ((select privado.sou_membro()));
create policy "configuracoes: dona altera" on public.configuracoes
  for update to authenticated
  using ((select privado.sou_dona()))
  with check ((select privado.sou_dona()));

-- Tabelas do dia a dia: Elita e ajudante leem, criam e alteram; só a Elita apaga.
do $$
declare
  t text;
begin
  foreach t in array array[
    'clientes', 'categorias', 'fornecedores', 'produtos', 'produto_fotos',
    'vendas', 'venda_itens', 'parcelas', 'pagamentos', 'ajustes', 'encomendas'
  ]
  loop
    execute format(
      'create policy "%1$s: membros leem" on public.%1$I for select to authenticated using ((select privado.sou_membro()))', t);
    execute format(
      'create policy "%1$s: membros criam" on public.%1$I for insert to authenticated with check ((select privado.sou_membro()))', t);
    execute format(
      'create policy "%1$s: membros alteram" on public.%1$I for update to authenticated using ((select privado.sou_membro())) with check ((select privado.sou_membro()))', t);
    execute format(
      'create policy "%1$s: so a dona apaga" on public.%1$I for delete to authenticated using ((select privado.sou_dona()))', t);
  end loop;
end;
$$;

-- CUSTO e GASTOS: só a Elita (ajudante não vê custo, lucro nem gastos).
create policy "produtos_custo: so a dona" on public.produtos_custo
  for all to authenticated
  using ((select privado.sou_dona()))
  with check ((select privado.sou_dona()));
create policy "gastos: so a dona" on public.gastos
  for all to authenticated
  using ((select privado.sou_dona()))
  with check ((select privado.sou_dona()));

-- =====================================================================
-- FOTOS (Storage): bucket privado "fotos"
-- =====================================================================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', false, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

create policy "fotos: membros veem" on storage.objects
  for select to authenticated
  using (bucket_id = 'fotos' and (select privado.sou_membro()));
create policy "fotos: membros enviam" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'fotos' and (select privado.sou_membro()));
create policy "fotos: membros trocam" on storage.objects
  for update to authenticated
  using (bucket_id = 'fotos' and (select privado.sou_membro()))
  with check (bucket_id = 'fotos' and (select privado.sou_membro()));
create policy "fotos: so a dona apaga" on storage.objects
  for delete to authenticated
  using (bucket_id = 'fotos' and (select privado.sou_dona()));
