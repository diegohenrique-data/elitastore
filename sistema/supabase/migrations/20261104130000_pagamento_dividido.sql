-- =====================================================================
-- Versão 1.8 (04/11/2026): PAGAMENTO EM MAIS DE UMA FORMA na venda.
-- Ex.: R$ 20 em dinheiro + R$ 30 no cartão. A venda fica com forma_pagamento = 'dividido'
-- e cada parte numa linha de venda_pagamentos (a soma é o total da venda).
-- No fiado (ELA PAGOU) não precisa mudar nada: cada pagamento já é uma linha em pagamentos.
-- Só ACRESCENTA: nada é apagado.
-- =====================================================================
alter table public.vendas drop constraint if exists vendas_forma_pagamento_check;
alter table public.vendas add constraint vendas_forma_pagamento_check
  check (forma_pagamento in ('dinheiro', 'pix', 'cartao', 'fiado', 'dividido'));

create table if not exists public.venda_pagamentos (
  id uuid primary key default gen_random_uuid(),
  venda_id uuid not null references public.vendas (id) on delete cascade,
  forma text not null check (forma in ('dinheiro', 'pix', 'cartao')),
  valor numeric(10, 2) not null check (valor > 0),
  criado_em timestamptz not null default now()
);
create index if not exists venda_pagamentos_venda_idx on public.venda_pagamentos (venda_id);

-- Mesmas regras das outras tabelas do dia a dia: Elita e ajudante leem, criam e alteram; só a Elita apaga.
-- (Apagar a venda leva as partes junto, pela função apagar_venda.)
alter table public.venda_pagamentos enable row level security;
create policy "venda_pagamentos: membros leem" on public.venda_pagamentos
  for select to authenticated using ((select privado.sou_membro()));
create policy "venda_pagamentos: membros criam" on public.venda_pagamentos
  for insert to authenticated with check ((select privado.sou_membro()));
create policy "venda_pagamentos: membros alteram" on public.venda_pagamentos
  for update to authenticated using ((select privado.sou_membro())) with check ((select privado.sou_membro()));
create policy "venda_pagamentos: so a dona apaga" on public.venda_pagamentos
  for delete to authenticated using ((select privado.sou_dona()));

revoke all on public.venda_pagamentos from anon;
grant select, insert, update, delete on public.venda_pagamentos to authenticated;
