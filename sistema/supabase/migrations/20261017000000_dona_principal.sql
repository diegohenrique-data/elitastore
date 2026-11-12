-- =====================================================================
-- Dona principal: a Elita (primeira conta cadastrada) é a ÚNICA dona.
-- - Não existe nenhuma conta acima dela.
-- - Ninguém pode tirar o acesso dela, rebaixar ou desligar (nem pela API).
-- - Todas as outras contas são ajudantes e só entram quando ela libera.
-- =====================================================================

alter table public.perfis add column if not exists principal boolean not null default false;

-- A primeira conta cadastrada vira a principal (hoje: Elita Mello).
update public.perfis set principal = true, papel = 'dona', ativo = true
where id = (select id from public.perfis order by criado_em limit 1);

-- Qualquer outra conta que estivesse como dona passa a ajudante.
update public.perfis set papel = 'ajudante' where not principal and papel = 'dona';

-- Só pode existir UMA principal, e "dona" = "principal".
create unique index if not exists perfis_uma_principal on public.perfis (principal) where principal;
alter table public.perfis drop constraint if exists perfis_dona_e_principal;
alter table public.perfis add constraint perfis_dona_e_principal check ((papel = 'dona') = principal);

-- Trava: a principal não pode ser rebaixada, desligada nem trocada; ninguém vira principal depois.
create or replace function privado.proteger_principal()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if old.principal and (new.principal is distinct from old.principal
                        or new.papel is distinct from old.papel
                        or new.ativo is distinct from old.ativo) then
    raise exception 'A dona principal da loja não pode ser alterada.';
  end if;
  if not old.principal and new.principal then
    raise exception 'Só existe uma dona principal.';
  end if;
  return new;
end;
$$;
revoke all on function privado.proteger_principal() from public, anon, authenticated;

drop trigger if exists proteger_principal on public.perfis;
create trigger proteger_principal
  before update on public.perfis
  for each row execute function privado.proteger_principal();

-- Novos cadastros: a primeira conta vira a principal; as outras, ajudante desligada.
create or replace function privado.criar_perfil()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if exists (select 1 from public.perfis) then
    insert into public.perfis (id, nome, papel, ativo, principal)
    values (new.id, coalesce(new.raw_user_meta_data ->> 'nome', ''), 'ajudante', false, false);
  else
    insert into public.perfis (id, nome, papel, ativo, principal)
    values (new.id, coalesce(new.raw_user_meta_data ->> 'nome', 'Elita'), 'dona', true, true);
  end if;
  return new;
end;
$$;
revoke all on function privado.criar_perfil() from public, anon, authenticated;
