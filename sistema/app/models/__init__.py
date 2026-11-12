"""MODELS: os dados da loja e as regras do negócio.

Cada arquivo cuida de um assunto e é o ÚNICO lugar que conversa com o banco (Supabase)
sobre ele. Os controllers chamam estas funções; as views nunca falam com o banco.
Toda função recebe `db`: a conexão de quem está logado (assim o RLS do banco vale sempre).
"""
