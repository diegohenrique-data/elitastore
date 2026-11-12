-- =====================================================================
-- Apagar venda (31/10/2026, ponto-49): quem vendeu apaga a própria venda; a Elita apaga todas.
-- A ajudante não apaga venda de fiado que já recebeu pagamento: isso fica com a Elita.
-- Tudo acontece junto: devolve o estoque, reabre a encomenda entregue e tira a venda
-- (itens e parcelas saem em cascata). Compra antiga nunca baixou o estoque, então não devolve.
-- =====================================================================
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
    where p.id = i.produto_id;
  end if;
  update public.encomendas set etapa = 'chegou', entregue_em = null where venda_id = alvo;
  delete from public.vendas where id = alvo;
  return 'ok';
end;
$$;

revoke all on function public.apagar_venda(uuid) from public, anon;
grant execute on function public.apagar_venda(uuid) to authenticated;
