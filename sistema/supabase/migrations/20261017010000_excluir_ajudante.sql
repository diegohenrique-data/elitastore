-- =====================================================================
-- Excluir ajudante: a Elita (dona principal) apaga o login de uma pessoa
-- da equipe (e-mail, senha e perfil) direto pelo app.
-- Proteções: só a dona chama; nunca apaga a dona principal nem a si mesma.
-- O perfil sai junto (on delete cascade). O que a pessoa cadastrou fica
-- na loja, só sem o nome de quem cadastrou (on delete set null).
-- =====================================================================
create or replace function public.excluir_ajudante(alvo uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not privado.sou_dona() then
    raise exception 'Só a dona da loja pode excluir alguém da equipe.';
  end if;
  if alvo = (select auth.uid()) then
    raise exception 'Você não pode excluir a sua própria conta.';
  end if;
  if exists (select 1 from public.perfis where id = alvo and principal) then
    raise exception 'A dona principal da loja não pode ser excluída.';
  end if;
  if not exists (select 1 from public.perfis where id = alvo) then
    raise exception 'Essa pessoa não está na equipe.';
  end if;
  delete from auth.users where id = alvo;
end;
$$;

revoke all on function public.excluir_ajudante(uuid) from public, anon;
grant execute on function public.excluir_ajudante(uuid) to authenticated;
