-- nome: affiliate_performance
-- params: janela_inicio, janela_fim
-- devolve: agregado por btag
-- fonte: risk_analytic_mcp/analytics.py::get_affiliate_performance (risk squads originais)
select
  coalesce(nullif(btag, ''), '(sem btag)') as btag,
  count(distinct player_id) as players,
  sum(turnover) as turnover,
  sum(ggr) as ggr,
  sum(total_apostas) as bets,
  sum(ggr) / nullif(sum(turnover), 0) as hold_pct,
  sum(turnover) / nullif(count(distinct player_id), 0) as turnover_per_player
from public.casino_activity
where dia between date %(janela_inicio)s and date %(janela_fim)s
group by coalesce(nullif(btag, ''), '(sem btag)')
order by turnover desc
