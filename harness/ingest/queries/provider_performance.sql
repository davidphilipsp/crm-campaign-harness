-- nome: provider_performance
-- params: janela_inicio, janela_fim
-- devolve: agregado por provider_name
-- fonte: risk_analytic_mcp/analytics.py::get_provider_performance (risk squads originais)
select
  provider_name,
  count(distinct player_id) as players,
  sum(turnover) as turnover,
  sum(ggr) as ggr,
  sum(total_apostas) as bets,
  sum(ggr) / nullif(sum(turnover), 0) as hold_pct,
  sum(turnover) / nullif(sum(sum(turnover)) over (), 0) as turnover_share_pct
from public.casino_activity
where dia between date %(janela_inicio)s and date %(janela_fim)s
group by provider_name
order by turnover desc
