-- Versão 1.5 (23/10/2026): a Elita escolhe o ícone (emoji) de cada categoria.
-- Vazio = o sistema escolhe sozinho pelo nome (Perfumes -> 🧴), como já era.
-- Só um emoji (curto); não é foto. As permissões (RLS) da tabela continuam as mesmas.
alter table public.categorias
  add column if not exists icone text
  check (icone is null or length(icone) between 1 and 16);
