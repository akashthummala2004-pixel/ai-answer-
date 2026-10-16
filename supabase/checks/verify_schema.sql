-- Read-only post-migration check for AI Answer Verification. Changes nothing.
-- Run from the ai-answer-verification folder:
--   npx supabase@2.121.0 db query --linked -f supabase/checks/verify_schema.sql
with t as (
  select c.oid, c.relrowsecurity, c.relforcerowsecurity
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relname = 'verifications' and c.relkind = 'r'
),
p as (
  select policyname, cmd, roles::text as roles, qual, with_check
  from pg_policies where schemaname = 'public' and tablename = 'verifications'
),
expected(policyname, cmd, needs_using, needs_check) as (
  values ('verifications_select_own', 'SELECT', true,  false),
         ('verifications_insert_own', 'INSERT', false, true),
         ('verifications_update_own', 'UPDATE', true,  true),
         ('verifications_delete_own', 'DELETE', true,  false)
)
select 'table public.verifications exists' as check_name, exists (select 1 from t) as ok, null::text as detail
union all
select 'row level security enabled', coalesce((select relrowsecurity from t), false), null
union all
select 'columns match application',
       (select count(*) = 5 from information_schema.columns
         where table_schema = 'public' and table_name = 'verifications'
           and (column_name, data_type) in (('id','uuid'), ('user_id','uuid'), ('created_at','timestamp with time zone'),
                                            ('updated_at','timestamp with time zone'), ('payload','jsonb'))),
       (select string_agg(column_name || ':' || data_type, ', ' order by ordinal_position)
          from information_schema.columns where table_schema = 'public' and table_name = 'verifications')
union all
select 'user_id references auth.users',
       exists (select 1 from pg_constraint where conrelid = 'public.verifications'::regclass and contype = 'f'
                 and confrelid = 'auth.users'::regclass),
       null
union all
select 'index verifications_user_created_idx',
       exists (select 1 from pg_indexes where schemaname = 'public' and indexname = 'verifications_user_created_idx'),
       null
union all
select 'policy ' || e.policyname || ' (' || e.cmd || ', authenticated, owner-only)',
       p.policyname is not null
         and p.roles = '{authenticated}'
         and (not e.needs_using or p.qual ilike '%user_id = ( SELECT auth.uid()%')
         and (not e.needs_check or p.with_check ilike '%user_id = ( SELECT auth.uid()%'),
       coalesce('roles=' || p.roles || ' using=' || coalesce(p.qual, '-') || ' check=' || coalesce(p.with_check, '-'), 'MISSING')
from expected e left join p on p.policyname = e.policyname
union all
select 'no extra policies', (select count(*) = 4 from p), (select string_agg(policyname, ', ') from p)
union all
select 'anon has no table privileges',
       not exists (select 1 from information_schema.role_table_grants
                    where table_schema = 'public' and table_name = 'verifications' and grantee = 'anon'),
       (select string_agg(privilege_type, ',') from information_schema.role_table_grants
         where table_schema = 'public' and table_name = 'verifications' and grantee = 'anon')
union all
select 'authenticated has select/insert/update/delete',
       (select count(distinct privilege_type) = 4 from information_schema.role_table_grants
         where table_schema = 'public' and table_name = 'verifications' and grantee = 'authenticated'
           and privilege_type in ('SELECT','INSERT','UPDATE','DELETE')),
       null
union all
select 'existing rows (informational)', true, (select count(*)::text from public.verifications);
