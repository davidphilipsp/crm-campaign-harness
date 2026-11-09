-- nome: game_performance
-- params: janela_inicio, janela_fim
-- devolve: agregado por game_name (extraido de top_jogos JSON)
-- fonte: risk_analytic_mcp/analytics.py::get_game_performance (risk squads originais)
select
  coalesce(game.value->>'game_name', game.value->>'name', game.key) as game_name,
  count(distinct player_id) as players,
  sum(turnover) as turnover,
  sum(ggr) as ggr,
  sum(total_apostas) as bets,
  sum(ggr) / nullif(sum(turnover), 0) as hold_pct
from public.casino_activity
cross join lateral jsonb_each(
  case
    when jsonb_typeof(top_jogos) = 'object' then top_jogos
    else '{}'::jsonb
  end
) as game(key, value)
where dia between date %(janela_inicio)s and date %(janela_fim)s
group by coalesce(game.value->>'game_name', game.value->>'name', game.key)
order by turnover desc nulls last, players desc
