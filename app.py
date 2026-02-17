import streamlit as st
import pandas as pd
import random
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor de Torneio Suíço", layout="wide")

# --- ESTRUTURA DE DADOS (MODELO) ---
if 'teams' not in st.session_state:
    st.session_state.teams = [] 
if 'rounds' not in st.session_state:
    st.session_state.rounds = [] 
if 'phase' not in st.session_state:
    st.session_state.phase = 'registration' 
if 'playoff_schedule' not in st.session_state:
    st.session_state.playoff_schedule = [] # Lista de rodadas do mata-mata
if 'champion' not in st.session_state:
    st.session_state.champion = None

# --- FUNÇÕES AUXILIARES ---

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

# --- LÓGICA DO MATA-MATA (NOVA) ---

def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    # Ordena seeds por mérito (Quem não teve bye fica na frente)
    seeds = get_sorted_rankings(qualified) 
    
    num_q = len(seeds)
    current_matches = []
    waiting_teams = [] # Times que ganharam Bye e esperam a proxima rodada
    round_name = ""

    # LÓGICA INICIAL BASEADA NO MANUAL
    if num_q == 4:
        round_name = "Semifinais"
        current_matches = [
            {'id': 'S1', 'home': seeds[0], 'away': seeds[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': seeds[1], 'away': seeds[2], 'label': 'Semi 2'}
        ]
        
    elif num_q == 5:
        round_name = "Wildcard (Repescagem)"
        # 1, 2 e 3 esperam
        waiting_teams = [seeds[0], seeds[1], seeds[2]] 
        current_matches = [
            {'id': 'WC', 'home': seeds[3], 'away': seeds[4], 'label': 'Repescagem'}
        ]
        
    elif num_q == 6:
        round_name = "Quartas de Final"
        # 1 e 2 esperam
        waiting_teams = [seeds[0], seeds[1]]
        current_matches = [
            {'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'}, # 4 vs 5
            {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'}  # 3 vs 6
        ]
        
    elif num_q == 7:
        round_name = "Quartas de Final"
        # 1 espera
        waiting_teams = [seeds[0]]
        current_matches = [
            {'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'},
            {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'},
            {'id': 'QFC', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas C'}
        ]
        
    elif num_q >= 8:
        seeds = seeds[:8] # Garante top 8
        round_name = "Quartas de Final"
        current_matches = [
            {'id': 'Q1', 'home': seeds[0], 'away': seeds[7], 'label': 'Quartas 1'},
            {'id': 'Q2', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas 2'},
            {'id': 'Q3', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas 3'},
            {'id': 'Q4', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas 4'}
        ]

    # Estrutura da rodada de playoff
    round_data = {
        'name': round_name,
        'matches': current_matches,
        'waiting': waiting_teams, # Times esperando na próxima fase
        'completed': False
    }
    
    st.session_state.playoff_schedule = [round_data]
    st.session_state.phase = 'playoff_gameplay'

def advance_playoff_round(results, waiting_teams):
    # results = lista de vencedores (objetos time)
    # waiting_teams = lista de times que estavam de bye (objetos time)
    
    next_matches = []
    next_waiting = []
    next_round_name = ""
    
    # Total de times disponíveis para a próxima fase
    pool = waiting_teams + results
    # Reordenar pool por seed original para garantir a lógica de pareamento se necessário
    # (Aqui simplificaremos usando a lógica de chaveamento fixa baseada na quantidade)
    
    count = len(pool)
    
    # LÓGICA DE CRIAÇÃO DA PRÓXIMA FASE
    if count == 2:
        next_round_name = "Grande Final"
        next_matches = [{'id': 'F', 'home': pool[0], 'away': pool[1], 'label': 'Final'}]
        
    elif count == 4:
        next_round_name = "Semifinais"
        # Lógica Específica: Seed 1 (que estava esperando ou venceu Q1) vs Pior Seed restante
        # Mas como a lista 'pool' pode estar misturada, vamos assumir o pareamento padrão de chaves:
        # Se vieram de 5 times (Wildcard): 1 vs Venc_WC, 2 vs 3
        # Se vieram de 6 times (Quartas): 1 vs Venc_QFA(4v5), 2 vs Venc_QFB(3v6)
        
        # Vamos ordenar pelo ID original (Seed) para saber quem é quem
        pool = get_sorted_rankings(pool) # Re-ordena por mérito original
        
        # Cruzamento Olímpico (1º vs 4º, 2º vs 3º dos que sobraram)
        next_matches = [
            {'id': 'S1', 'home': pool[0], 'away': pool[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': pool[1], 'away': pool[2], 'label': 'Semi 2'}
        ]
        
    else:
        # Fallback genérico (caso raro de números estranhos, pareia olímpico)
        next_round_name = "Rodada Eliminatória"
        pool = get_sorted_rankings(pool)
        while len(pool) >= 2:
            home = pool.pop(0)
            away = pool.pop(-1)
            next_matches.append({'id': 'GEN', 'home': home, 'away': away, 'label': 'Jogo'})
            
    if not next_matches and count == 1:
        # CAMPEÃO DEFINIDO
        st.session_state.champion = pool[0]
        st.session_state.phase = 'champion'
        return

    new_round_data = {
        'name': next_round_name,
        'matches': next_matches,
        'waiting': next_waiting,
        'completed': False
    }
    st.session_state.playoff_schedule.append(new_round_data)

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
            
        submitted = st.form_submit_button("Confirmar Resultados e Encerrar Rodada")
        
        if submitted:
            if bye_team:
                update_team_stats(bye_team['id'], 1, 0, is_bye=True)
            
            for res in results:
                m = matches[res['match_idx']]
                update_team_stats(m['home'], res['h_score'], res['a_score'])
                update_team_stats(m['away'], res['a_score'], res['h_score'])
            
            active_count = len([t for t in st.session_state.teams if t['status'] == 'Ativo'])
            
            if active_count <= 1:
                init_playoffs() # INICIA O MATA-MATA
                st.rerun()
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
            'Teve Bye?': 'Sim' if t['received_bye'] else 'Não'
        })
    st.dataframe(pd.DataFrame(display_data), use_container_width=True)

# --- FASE 3: MATA-MATA (JOGÁVEL) ---
elif st.session_state.phase == 'playoff_gameplay':
    st.header("🔥 Fase Final (Mata-Mata)")
    
    current_round = st.session_state.playoff_schedule[-1]
    st.subheader(f"Etapa Atual: {current_round['name']}")
    
    if current_round['waiting']:
        names_waiting = ", ".join([t['name'] for t in current_round['waiting']])
        st.info(f"🛑 Times aguardando na próxima fase (Byes): **{names_waiting}**")
    
    # Formulário de Resultados do Mata-Mata
    # Usamos container para refresh dinâmico nos pênaltis se necessário
    
    winners = []
    all_decided = True
    
    with st.form(key=f"playoff_form_{len(st.session_state.playoff_schedule)}"):
        matches_results = []
        
        for i, match in enumerate(current_round['matches']):
            home = match['home']
            away = match['away']
            
            st.markdown(f"#### {match['label']}")
            col1, col2, col3, col4, col5 = st.columns([3, 1, 0.5, 1, 3])
            
            with col1: st.markdown(f"<h3 style='text-align: right'>{home['name']}</h3>", unsafe_allow_html=True)
            with col2: score_h = st.number_input("Gols", min_value=0, key=f"p_h_{i}")
            with col3: st.markdown("<h3 style='text-align: center'>X</h3>", unsafe_allow_html=True)
            with col4: score_a = st.number_input("Gols", min_value=0, key=f"p_a_{i}")
            with col5: st.markdown(f"<h3>{away['name']}</h3>", unsafe_allow_html=True)
            
            # LÓGICA DE PÊNALTIS
            pen_h = 0
            pen_a = 0
            winner = None
            
            # Se houver empate, mostramos input de penaltis
            # Nota: No Streamlit forms, a UI não atualiza instantaneamente sem rerun.
            # Vamos pedir para preencher penaltis SEMPRE que for empate visualmente
            if score_h == score_a:
                st.warning(f"⚠️ Empate! Insira o resultado dos pênaltis para {home['name']} vs {away['name']}")
                cp1, cp2 = st.columns(2)
                with cp1: pen_h = st.number_input(f"Pênaltis {home['name']}", min_value=0, key=f"pen_h_{i}")
                with cp2: pen_a = st.number_input(f"Pênaltis {away['name']}", min_value=0, key=f"pen_a_{i}")
                
                if pen_h == pen_a:
                    st.error("Os pênaltis não podem terminar empatados!")
                    all_decided = False
                elif pen_h > pen_a:
                    winner = home
                else:
                    winner = away
            elif score_h > score_a:
                winner = home
            else:
                winner = away
                
            matches_results.append(winner)
        
        submitted = st.form_submit_button("Confirmar Resultados do Mata-Mata")
        
        if submitted:
            if all_decided:
                advance_playoff_round(matches_results, current_round['waiting'])
                st.rerun()
            else:
                st.error("Por favor, resolva os empates nos pênaltis antes de continuar.")

# --- FASE 4: CAMPEÃO ---
elif st.session_state.phase == 'champion':
    st.balloons()
    champ = st.session_state.champion
    
    st.markdown(f"""
    <div style="text-align: center; padding: 50px;">
        <h1>🏆 TEMOS UM CAMPEÃO! 🏆</h1>
        <h2 style="color: gold; font-size: 60px;">{champ['name']}</h2>
        <p>Parabéns pela campanha incrível!</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Reiniciar Torneio Completo"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
