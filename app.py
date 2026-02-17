import streamlit as st
import pandas as pd
import random

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor de Torneio Suíço", layout="wide")

# --- ESTRUTURA DE DADOS (MODELO) ---
if 'teams' not in st.session_state:
    st.session_state.teams = [] 
if 'rounds' not in st.session_state:
    st.session_state.rounds = [] 
if 'phase' not in st.session_state:
    st.session_state.phase = 'registration' 
if 'playoff_matches' not in st.session_state:
    st.session_state.playoff_matches = []
if 'playoff_history' not in st.session_state:
    st.session_state.playoff_history = []
if 'seeds' not in st.session_state:
    st.session_state.seeds = [] # Armazena os classificados ordenados

# --- FUNÇÕES AUXILIARES DE LÓGICA ---

def get_sorted_rankings(teams, for_pairing=False):
    # REGRA: Vitórias > Bye (False > True) > Saldo > Gols Pró
    if for_pairing:
        random.shuffle(teams)
    
    return sorted(teams, key=lambda x: (
        x['wins'], 
        not x['received_bye'], 
        x['goal_diff'], 
        x['goals_for']
    ), reverse=True)

def update_team_stats(team_id, goals_scored, goals_conceded, is_bye=False):
    for team in st.session_state.teams:
        if team['id'] == team_id:
            team['goals_for'] += goals_scored
            team['goal_diff'] += (goals_scored - goals_conceded)
            if goals_scored > goals_conceded or is_bye:
                team['wins'] += 1
            else:
                team['losses'] += 1
            
            if is_bye:
                team['received_bye'] = True
            
            # ATUALIZAÇÃO DE STATUS
            if team['wins'] >= 3:
                team['status'] = 'Classificado'
            elif team['losses'] >= 3:
                team['status'] = 'Eliminado'
            break

def generate_swiss_round():
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    
    # REGRA: BYE (NÚMERO ÍMPAR)
    bye_team = None
    if len(active_teams) % 2 != 0:
        worst_sorted = sorted(active_teams, key=lambda x: (
            x['wins'], 
            not x['received_bye'], 
            x['goal_diff']
        ))
        
        for t in worst_sorted:
            if not t['received_bye']:
                bye_team = t
                break
        
        if not bye_team:
            bye_team = worst_sorted[0]
            
        active_teams.remove(bye_team)

    # PAREAMENTO
    ranked_pool = get_sorted_rankings(active_teams, for_pairing=True)
    matches = []
    
    while len(ranked_pool) >= 2:
        home = ranked_pool.pop(0)
        opponent = None
        for i, candidate in enumerate(ranked_pool):
            if candidate['id'] not in home['history']:
                opponent = ranked_pool.pop(i)
                break
        
        if not opponent:
            opponent = ranked_pool.pop(0)
            
        matches.append({
            'home': home['id'], 'away': opponent['id'], 
            'home_score': 0, 'away_score': 0
        })
        
        home['history'].append(opponent['id'])
        opponent['history'].append(home['id'])

    st.session_state.rounds.append({'matches': matches, 'bye': bye_team})

def start_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    # Ordena seeds por mérito
    seeds = get_sorted_rankings(qualified)
    st.session_state.seeds = seeds
    
    num_q = len(seeds)
    matchups = []
    
    # GERA A PRIMEIRA RODADA DO MATA-MATA (Dependendo do número de times)
    if num_q == 4:
        # Já vai para Semi
        matchups = [
            {'round': 'Semifinal', 'id': 'semi1', 'home': seeds[0], 'away': seeds[3]},
            {'round': 'Semifinal', 'id': 'semi2', 'home': seeds[1], 'away': seeds[2]}
        ]
    elif num_q == 5:
        # Wildcard
        matchups = [
            {'round': 'Wildcard', 'id': 'wild1', 'home': seeds[3], 'away': seeds[4]}
        ]
    elif num_q == 6:
        # Quartas (1 e 2 folgam)
        matchups = [
            {'round': 'Quartas de Final', 'id': 'qf_a', 'home': seeds[3], 'away': seeds[4]}, # 4 vs 5
            {'round': 'Quartas de Final', 'id': 'qf_b', 'home': seeds[2], 'away': seeds[5]}  # 3 vs 6
        ]
    elif num_q == 7:
        # Quartas (Só 1 folga)
        matchups = [
            {'round': 'Quartas de Final', 'id': 'qf_a', 'home': seeds[3], 'away': seeds[4]},
            {'round': 'Quartas de Final', 'id': 'qf_b', 'home': seeds[2], 'away': seeds[5]},
            {'round': 'Quartas de Final', 'id': 'qf_c', 'home': seeds[1], 'away': seeds[6]}
        ]
    elif num_q >= 8:
        # Quartas Completas
        s = seeds[:8]
        matchups = [
            {'round': 'Quartas de Final', 'id': 'qf1', 'home': s[0], 'away': s[7]},
            {'round': 'Quartas de Final', 'id': 'qf2', 'home': s[1], 'away': s[6]},
            {'round': 'Quartas de Final', 'id': 'qf3', 'home': s[2], 'away': s[5]},
            {'round': 'Quartas de Final', 'id': 'qf4', 'home': s[3], 'away': s[4]}
        ]
    
    st.session_state.playoff_matches = matchups
    st.session_state.phase = 'playoff'

def advance_playoff_round(results):
    # results é um dicionário: {'id_do_jogo': objeto_time_vencedor}
    
    current_matches = st.session_state.playoff_matches
    seeds = st.session_state.seeds
    num_q = len(seeds)
    next_matches = []
    
    # Salva histórico
    st.session_state.playoff_history.extend(current_matches)
    
    # LÓGICA DE AVANÇO DE FASE
    
    # --- CENÁRIO: Fim da FINAL ---
    if current_matches[0]['round'] == 'Grande Final':
        winner = results['final']
        st.session_state.champion = winner
        st.session_state.phase = 'finished'
        return

    # --- CENÁRIO: Fim das SEMIFINAIS ---
    if current_matches[0]['round'] == 'Semifinal':
        # Quem venceu as semis vai para a final
        # Ordem dos matches na lista de Semis é sempre [Semi1, Semi2]
        w1 = results.get('semi1')
        w2 = results.get('semi2')
        
        # Caso especial do Wildcard ou Quartas onde o ID pode variar, pegamos pela ordem
        if not w1 or not w2: 
            # Fallback: pega os dois vencedores disponíveis
            winners_list = list(results.values())
            w1, w2 = winners_list[0], winners_list[1]
            
        next_matches = [
            {'round': 'Grande Final', 'id': 'final', 'home': w1, 'away': w2}
        ]

    # --- CENÁRIO: Fim do WILDCARD (5 times) ---
    elif current_matches[0]['round'] == 'Wildcard':
        w_wild = results['wild1']
        next_matches = [
            {'round': 'Semifinal', 'id': 'semi1', 'home': seeds[0], 'away': w_wild}, # 1 vs Venc. Wild
            {'round': 'Semifinal', 'id': 'semi2', 'home': seeds[1], 'away': seeds[2]}  # 2 vs 3
        ]

    # --- CENÁRIO: Fim das QUARTAS ---
    elif current_matches[0]['round'] == 'Quartas de Final':
        # Caso 6 Times
        if num_q == 6:
            wa = results['qf_a']
            wb = results['qf_b']
            next_matches = [
                {'round': 'Semifinal', 'id': 'semi1', 'home': seeds[0], 'away': wa}, # 1 vs (4v5)
                {'round': 'Semifinal', 'id': 'semi2', 'home': seeds[1], 'away': wb}  # 2 vs (3v6)
            ]
        
        # Caso 7 Times
        elif num_q == 7:
            wa = results['qf_a']
            wb = results['qf_b']
            wc = results['qf_c']
            next_matches = [
                {'round': 'Semifinal', 'id': 'semi1', 'home': seeds[0], 'away': wa}, # 1 vs (4v5)
                {'round': 'Semifinal', 'id': 'semi2', 'home': wc, 'away': wb}        # (2v7) vs (3v6) - Ajustado lógica
            ]
            
        # Caso 8 Times
        elif num_q >= 8:
            w1 = results['qf1'] # 1 vs 8
            w2 = results['qf2'] # 2 vs 7
            w3 = results['qf3'] # 3 vs 6
            w4 = results['qf4'] # 4 vs 5
            next_matches = [
                {'round': 'Semifinal', 'id': 'semi1', 'home': w1, 'away': w4},
                {'round': 'Semifinal', 'id': 'semi2', 'home': w2, 'away': w3}
            ]

    st.session_state.playoff_matches = next_matches

# --- INTERFACE GRÁFICA ---

st.title("🏆 Gerenciador de Torneio Suíço (Triple Elimination)")

# --- FASE 1: INSCRIÇÃO ---
if st.session_state.phase == 'registration':
    st.header("1. Inscrição de Times")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_team = st.text_input("Nome do Time")
    with col2:
        if st.button("Adicionar"):
            if new_team and new_team not in [t['name'] for t in st.session_state.teams]:
                t_obj = {
                    'id': len(st.session_state.teams) + 1,
                    'name': new_team,
                    'wins': 0, 'losses': 0,
                    'goals_for': 0, 'goal_diff': 0,
                    'received_bye': False,
                    'history': [],
                    'status': 'Ativo'
                }
                st.session_state.teams.append(t_obj)
                st.success(f"{new_team} adicionado!")
            elif not new_team:
                st.warning("Digite um nome.")
            else:
                st.error("Time já existe.")

    if st.session_state.teams:
        df_teams = pd.DataFrame(st.session_state.teams)
        st.dataframe(df_teams[['name', 'status']], use_container_width=True)
    
    st.markdown("---")
    if st.button("Iniciar Torneio"):
        qtd = len(st.session_state.teams)
        if 6 <= qtd <= 16:
            st.session_state.phase = 'swiss'
            generate_swiss_round()
            st.rerun()
        else:
            st.error(f"É necessário entre 6 e 16 times. Atual: {qtd}")

# --- FASE 2: SUÍÇO ---
elif st.session_state.phase == 'swiss':
    round_idx = len(st.session_state.rounds)
    st.header(f"Fase Suíça - Rodada {round_idx}")
    
    current_round = st.session_state.rounds[-1]
    matches = current_round['matches']
    bye_team = current_round['bye']
    
    if bye_team:
        st.info(f"🎉 BYE: O time **{bye_team['name']}** folga nesta rodada e ganha +1 Vitória.")

    with st.form(key=f"round_form_{round_idx}"):
        st.subheader("Resultados dos Jogos")
        
        results = []
        for i, match in enumerate(matches):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
            
            home_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['home'])
            away_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['away'])
            
            with c1: st.markdown(f"<h3 style='text-align: right'>{home_name}</h3>", unsafe_allow_html=True)
            with c2: s1 = st.number_input("Gols", min_value=0, key=f"h_{round_idx}_{i}")
            with c3: s2 = st.number_input("Gols", min_value=0, key=f"a_{round_idx}_{i}")
            with c4: st.markdown(f"<h3>{away_name}</h3>", unsafe_allow_html=True)
            
            results.append({'match_idx': i, 'h_score': s1, 'a_score': s2})
            
        submitted = st.form_submit_button("Confirmar Rodada")
        
        if submitted:
            if bye_team:
                update_team_stats(bye_team['id'], 1, 0, is_bye=True)
            
            for res in results:
                m = matches[res['match_idx']]
                update_team_stats(m['home'], res['h_score'], res['a_score'])
                update_team_stats(m['away'], res['a_score'], res['h_score'])
            
            active_count = len([t for t in st.session_state.teams if t['status'] == 'Ativo'])
            
            if active_count <= 1:
                start_playoffs()
            else:
                generate_swiss_round()
            
            st.rerun()

    st.markdown("### Classificação Atual")
    sorted_teams = get_sorted_rankings(st.session_state.teams)
    
    display_data = []
    for t in sorted_teams:
        display_data.append({
            'Time': t['name'],
            'Status': t['status'],
            'V': t['wins'],
            'D': t['losses'],
            'Saldo': t['goal_diff'],
            'GP': t['goals_for'],
            'Teve Bye?': 'Sim' if t['received_bye'] else 'Não'
        })
    st.dataframe(pd.DataFrame(display_data), use_container_width=True)

# --- FASE 3: MATA-MATA (JOGÁVEL) ---
elif st.session_state.phase == 'playoff':
    
    current_matches = st.session_state.playoff_matches
    round_name = current_matches[0]['round']
    
    st.header(f"🔥 Fase Final: {round_name}")

    # Lista de Vencedores da rodada anterior (Histórico visual)
    if st.session_state.playoff_history:
        with st.expander("Ver jogos anteriores"):
            for old_match in st.session_state.playoff_history:
                h = old_match['home']['name']
                a = old_match['away']['name']
                st.write(f"{old_match['round']}: {h} vs {a}")

    with st.form(key=f"playoff_form_{round_name}"):
        
        round_winners = {}
        
        for i, match in enumerate(current_matches):
            home_team = match['home']
            away_team = match['away']
            
            st.markdown(f"---")
            c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
            
            with c1: st.markdown(f"<h3 style='text-align: right'>{home_team['name']}</h3>", unsafe_allow_html=True)
            with c2: h_goals = st.number_input("Gols", min_value=0, key=f"p_h_{i}")
            with c3: a_goals = st.number_input("Gols", min_value=0, key=f"p_a_{i}")
            with c4: st.markdown(f"<h3>{away_team['name']}</h3>", unsafe_allow_html=True)
            
            # LÓGICA DE PÊNALTIS E EMPATE
            winner = None
            if h_goals > a_goals:
                winner = home_team
                st.success(f"Vencedor: {home_team['name']}")
            elif a_goals > h_goals:
                winner = away_team
                st.success(f"Vencedor: {away_team['name']}")
            else:
                # Empate -> Pênaltis
                st.warning("⚠️ Empate! Decisão por Pênaltis:")
                penalty_choice = st.radio(
                    f"Quem venceu nos pênaltis no jogo {home_team['name']} vs {away_team['name']}?",
                    options=[home_team['name'], away_team['name']],
                    key=f"pen_{i}"
                )
                if penalty_choice == home_team['name']:
                    winner = home_team
                else:
                    winner = away_team
            
            # Armazena o vencedor pelo ID do jogo (ex: 'semi1', 'qf_a')
            if match.get('id'):
                round_winners[match['id']] = winner
            else:
                # Fallback para finais ou jogos unicos
                round_winners['final'] = winner

        st.markdown("---")
        if st.form_submit_button("Confirmar Resultados e Avançar"):
            advance_playoff_round(round_winners)
            st.rerun()

# --- FASE 4: CAMPEÃO ---
elif st.session_state.phase == 'finished':
    st.balloons()
    st.markdown("<h1 style='text-align: center'>🏆 TEMOS UM CAMPEÃO! 🏆</h1>", unsafe_allow_html=True)
    
    champion = st.session_state.champion
    st.markdown(f"<h2 style='text-align: center; color: gold'>{champion['name']}</h2>", unsafe_allow_html=True)
    
    st.image("https://media
