-- nome: payment_field_profile
-- params: sample_size
-- devolve: agregado por key (contagem de chaves JSON em payments_source)
-- fonte: risk_analytic_mcp/analytics.py::get_payment_field_profile (risk squads originais)
select key, count(*) as occurrences
from (
  select json_data
  from public.payments_source
  limit %(sample_size)s
) sample
cross join lateral jsonb_object_keys(json_data) as key
group by key
order by occurrences desc, key
