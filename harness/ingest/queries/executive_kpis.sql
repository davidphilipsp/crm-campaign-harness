-- nome: executive_kpis
-- params: janela_inicio, janela_fim
-- devolve: agregado por periodo (turnover, ggr, players, apostas)
-- fonte: risk_analytic_mcp/analytics.py::get_executive_kpis (risk squads originais)
select
  min(dia) as min_dia,
  max(dia) as max_dia,
  count(distinct provider_name) as providers,
  count(distinct player_id) as players,
  sum(turnover) as turnover,
  sum(ggr) as ggr,
  sum(total_apostas) as bets
from public.casino_activity
where dia between date %(janela_inicio)s and date %(janela_fim)s
