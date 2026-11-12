-- 28/10/2026 (ponto-38): a aba FORNECEDORES saiu do sistema, a pedido do Tiago.
-- Tira o vínculo dos produtos e das encomendas com o fornecedor e apaga a tabela.
-- Antes de rodar, a tabela estava VAZIA (nenhum fornecedor, nenhum produto ou encomenda ligado).
-- Para desfazer: recriar a tabela e os 2 campos como na 20261016222526_estrutura_inicial.sql.
alter table public.produtos drop column if exists fornecedor_id;
alter table public.encomendas drop column if exists fornecedor_id;
drop table if exists public.fornecedores;
