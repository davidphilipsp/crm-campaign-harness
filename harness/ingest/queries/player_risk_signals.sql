-- nome: player_risk_signals
-- params: janela_inicio, janela_fim
-- devolve: agregado por player_id
-- fonte: risk_analytic_mcp/analytics.py::get_player_risk_signals (risk squads originais)
select
  player_id,
  min(dia) as first_day,
  max(dia) as last_day,
  count(distinct dia) as active_days,
  count(distinct provider_name) as providers_used,
  sum(turnover) as turnover,
  sum(ggr) as ggr,
  sum(total_apostas) as bets,
  sum(turnover) / nullif(sum(total_apostas), 0) as avg_bet,
  sum(ggr) / nullif(sum(turnover), 0) as hold_pct
from public.casino_activity
where dia between date %(janela_inicio)s and date %(janela_fim)s
group by player_id
order by abs(sum(ggr)) desc, sum(turnover) desc
