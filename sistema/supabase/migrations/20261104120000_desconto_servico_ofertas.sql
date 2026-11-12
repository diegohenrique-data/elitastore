-- =====================================================================
-- Versão 1.8 (04/11/2026), pedidos da cliente. Só ACRESCENTA campos: nada é apagado.
-- 1. DESCONTO na venda: no produto (venda_itens.desconto = desconto da linha toda, em R$)
--    e na compra toda (vendas.desconto, em R$). vendas.total já vem com os descontos tirados.
-- 2. SERVIÇO (escova, chapinha, progressiva, manicure...): produtos.servico = não tem estoque.
--    Vende quantas vezes quiser, não entra nos avisos de estoque e não volta estoque ao apagar a venda.
-- 3. EXCLUIR PESSOA: quem já comprou fica guardada escondida (clientes.ativo = false), para o
--    histórico e o Meu Dinheiro continuarem certos. Quem nunca comprou é apagada de verdade.
-- =====================================================================
alter table public.vendas
  add column if not exists desconto numeric(10, 2) not null default 0 check (desconto >= 0);
alter table public.venda_itens
  add column if not exists desconto numeric(10, 2) not null default 0 check (desconto >= 0);
alter table public.produtos
  add column if not exists servico boolean not null default false;
alter table public.clientes
  add column if not exists ativo boolean not null default true;

-- A view do fiado passa a dizer se a pessoa está na lista (coluna nova no fim).
create or replace view public.clientes_saldo
with (security_invoker = true)
as
select
  cl.id as cliente_id,
  cl.nome,
  cl.whatsapp,
  coalesce(sum(ps.falta), 0) as falta_total,
  coalesce(sum(ps.falta) filter (where ps.situacao = 'atrasada'), 0) as atrasado,
  coalesce(sum(ps.falta) filter (where ps.situacao = 'hoje'), 0) as hoje,
  min(ps.vencimento) filter (where ps.situacao <> 'paga') as proximo_vencimento,
  cl.ativo
from public.clientes cl
left join public.parcelas_situacao ps on ps.cliente_id = cl.id
group by cl.id, cl.nome, cl.whatsapp, cl.ativo;

-- Apagar venda: igual à de 31/10/2026, mas SERVIÇO não volta para o estoque.
create or replace function public.apagar_venda(alvo uuid)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v record;
begin
  if not privado.sou_membro() then
    return 'sem_permissao';
  end if;
  select id, vendido_por, observacao into v from public.vendas where id = alvo for update;
  if not found then
    return 'nao_existe';
  end if;
  if not privado.sou_dona() then
    if v.vendido_por is distinct from (select auth.uid()) then
      return 'sem_permissao';
    end if;
    if exists (select 1 from public.parcelas_situacao where venda_id = alvo and pago > 0) then
      return 'tem_pagamento';
    end if;
  end if;
  if v.observacao is distinct from 'Compra antiga (anotada depois)' then
    update public.produtos p set quantidade = p.quantidade + i.qtd
    from (select produto_id, sum(quantidade) as qtd from public.venda_itens
          where venda_id = alvo and produto_id is not null group by produto_id) i
    where p.id = i.produto_id and not p.servico;
  end if;
  update public.encomendas set etapa = 'chegou', entregue_em = null where venda_id = alvo;
  delete from public.vendas where id = alvo;
  return 'ok';
end;
$$;

revoke all on function public.apagar_venda(uuid) from public, anon;
grant execute on function public.apagar_venda(uuid) to authenticated;

-- Vender serviço não mexe no estoque (o serviço não tem estoque).
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
      where id = new.produto_id and not servico;
  end if;
  return new;
end;
$$;
revoke all on function public.baixar_estoque() from public, anon;
