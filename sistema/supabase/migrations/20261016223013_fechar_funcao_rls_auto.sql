-- A opção "Enable automatic RLS" do Supabase cria a função public.rls_auto_enable()
-- (usada por um event trigger). Ninguém precisa chamá-la pela API: fechamos o acesso.
-- O event trigger continua funcionando, porque ele não depende dessa permissão.
revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
