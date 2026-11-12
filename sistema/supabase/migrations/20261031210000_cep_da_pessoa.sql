-- 31/10/2026 (ponto-48): o endereço da pessoa vem do CEP. Guarda o CEP e o número para reabrir o cadastro.
-- O endereço completo continua em clientes.endereco. Pessoa sem CEP: os dois ficam vazios.
alter table public.clientes
  add column if not exists cep text not null default '',
  add column if not exists numero text not null default '';
