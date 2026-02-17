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
if 'playoff_schedule' not in st.session_state:
    st.session_state.playoff_schedule = [] 
if 'champion' not in st.session_state:
    st.session_state.champion = None
# Controles de estado para formulários de duas etapas (Pênaltis)
if 'swiss_asking_penalties' not in st.session_state:
    st.session_state.swiss_asking_penalties = False 
if 'playoff_asking_penalties' not in st.session_state:
    st.session_state.playoff_asking_penalties = False 

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

def update_team_stats(team_id, goals_scored, goals_conceded, is_winner, is_bye=False):
    for team in st.session_state.teams:
        if team['id'] == team_id:
            team['goals_for'] += goals_scored
            team['goal_diff'] += (goals_scored - goals_conceded)
            
            if is_winner:
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

def render_sidebar_stats():
    """Função para mostrar o histórico detalhado na barra lateral"""
    with st.sidebar:
        st.header("📊 Classificação")
        if st.session_state.teams:
            sorted_teams = get_sorted_rankings(st.session_state.teams, for_pairing=False)
            
            display_data = []
            for t in sorted_teams:
                # Calcula gols contra na hora (GP - Saldo)
                goals_against = t['goals_for'] - t['goal_diff']
                
                display_data.append({
                    'Time': t['name'],
                    'V-D': f"{t['wins']}-{t['losses']}",
                    'GP': t['goals_for'],
                    'GC': goals_against,
                    'SG': t['goal_diff']
                })
            
            df = pd.DataFrame(display_data)
            
            # Configuração visual da tabela para ficar compacta
            st.dataframe(
                df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Time": st.column_config.TextColumn("Time", width="medium"),
                    "V-D": st.column_config.TextColumn("V-D", width="small"),
                    "GP": st.column_config.NumberColumn("GP", format="%d"),
                    "GC": st.column_config.NumberColumn("GC", format="%d"),
                    "SG": st.column_config.NumberColumn("SG", format="%d"),
                }
            )
            
            st.caption("GP: Gols Pró | GC: Gols Contra | SG: Saldo")
            
            # Legenda de Status
            st.markdown("---")
            st.markdown("**Legenda de Status:**")
            st.markdown("🟢 Classificado (3 Vitórias)")
            st.markdown("🔴 Eliminado (3 Derrotas)")
            st.markdown("⚪ Em Jogo")

# --- LÓGICA DO SUIÇO ---

def generate_swiss_round():
    st.session_state.swiss_asking_penalties = False 
    
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    random.shuffle(active_teams) 
    
    # BYE
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

# --- LÓGICA DO MATA-MATA ---

def init_playoffs():
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified, for_pairing=False) 
    
    num_q = len(seeds)
    current_matches = []
    waiting_teams = [] 
    round_name = ""

    if num_q == 3:
        round_name = "Semifinal Única"
        waiting_teams = [seeds[0]] 
        current_matches = [{'id': 'S1', 'home': seeds[1], 'away': seeds[2], 'label': 'Semifinal'}]
    elif num_q == 4:
        round_name = "Semifinais"
        current_matches = [
            {'id': 'S1', 'home': seeds[0], 'away': seeds[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': seeds[1], 'away': seeds[2], 'label': 'Semi 2'}
        ]
    elif num_q == 5:
        round_name = "Wildcard (Repescagem)"
        waiting_teams = [seeds[0], seeds[1], seeds[2]] 
        current_matches = [{'id': 'WC', 'home': seeds[3], 'away': seeds[4], 'label': 'Repescagem'}]
    elif num_q == 6:
        round_name = "Quartas de Final"
        waiting_teams = [seeds[0], seeds[1]]
        current_matches = [
            {'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'},
            {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'}
        ]
    elif num_q == 7:
        round_name = "Quartas de Final"
        waiting_teams = [seeds[0]]
        current_matches = [
            {'id': 'QFA', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas A'},
            {'id': 'QFB', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas B'},
            {'id': 'QFC', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas C'}
        ]
    elif num_q >= 8:
        seeds = seeds[:8]
        round_name = "Quartas de Final"
        current_matches = [
            {'id': 'Q1', 'home': seeds[0], 'away': seeds[7], 'label': 'Quartas 1'},
            {'id': 'Q2', 'home': seeds[1], 'away': seeds[6], 'label': 'Quartas 2'},
            {'id': 'Q3', 'home': seeds[2], 'away': seeds[5], 'label': 'Quartas 3'},
            {'id': 'Q4', 'home': seeds[3], 'away': seeds[4], 'label': 'Quartas 4'}
        ]
    
    if num_q < 3:
         st.error(f"Erro Crítico: Apenas {num_q} classificados. O sistema precisa de no mínimo 3.")
         return

    for m in current_matches:
        m['h_goals'] = 0
        m['a_goals'] = 0
        m['h_pen'] = 0
        m['a_pen'] = 0

    round_data = {
        'name': round_name,
        'matches': current_matches,
        'waiting': waiting_teams,
        'completed': False
    }
    
    st.session_state.playoff_schedule = [round_data]
    st.session_state.phase = 'playoff_gameplay'
    st.session_state.playoff_asking_penalties = False

def advance_playoff_round(results, waiting_teams):
    st.session_state.playoff_asking_penalties = False 
    
    pool = waiting_teams + results
    count = len(pool)
    
    next_matches = []
    next_round_name = ""
    
    if count == 2:
        next_round_name = "Grande Final"
        pool = get_sorted_rankings(pool, for_pairing=False)
        next_matches = [{'id': 'F', 'home': pool[0], 'away': pool[1], 'label': 'Final'}]
        
    elif count == 4:
        next_round_name = "Semifinais"
        pool = get_sorted_rankings(pool, for_pairing=False)
        next_matches = [
            {'id': 'S1', 'home': pool[0], 'away': pool[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': pool[1], 'away': pool[2], 'label': 'Semi 2'}
        ]
    else:
        next_round_name = "Rodada Eliminatória"
        pool = get_sorted_rankings(pool, for_pairing=False)
        while len(pool) >= 2:
            home = pool.pop(0)
            away = pool.pop(-1)
            next_matches.append({'id': 'GEN', 'home': home, 'away': away, 'label': 'Jogo'})
            
    if not next_matches and count == 1:
        st.session_state.champion = pool[0]
        st.session_state.phase = 'champion'
        return

    for m in next_matches:
        m['h_goals'] = 0
        m['a_goals'] = 0
        m['h_pen'] = 0
        m['a_pen'] = 0

    new_round_data = {
        'name': next_round_name,
        'matches': next_matches,
        'waiting': [],
        'completed': False
    }
    st.session_state.playoff_schedule.append(new_round_data)

# --- APP PRINCIPAL ---

def add_team_callback():
    new_team = st.session_state.team_input
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
        st.session_state.team_input = "" 
    elif not new_team:
        st.warning("Digite um nome.")
    else:
        st.error("Time já existe.")

if st.session_state.phase == 'registration':
    st.title("🏆 Inscrição de Times")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.text_input("Nome do Time", key="team_input")
    with col2:
        st.button("Adicionar", on_click=add_team_callback)

    if st.session_state.teams:
        st.markdown(f"**Total de Inscritos: {len(st.session_state.teams)}**")
    
    st.markdown("---")
    if st.button("Iniciar Torneio"):
        qtd = len(st.session_state.teams)
        if 6 <= qtd <= 16:
            st.session_state.phase = 'swiss'
            generate_swiss_round()
            st.rerun()
        else:
            st.error(f"É necessário entre 6 e 16 times. Atual: {qtd}")

elif st.session_state.phase == 'swiss':
    round_idx = len(st.session_state.rounds)
    st.title(f"⚔️ Fase Suíça - Rodada {round_idx}")
    
    current_round = st.session_state.rounds[-1]
    matches = current_round['matches']
    bye_team = current_round['bye']
    
    if bye_team:
        st.success(f"🎉 **BYE:** O time **{bye_team['name']}** folga e ganha +1 Vitória.")

    with st.form(key=f"swiss_round_form_{round_idx}"):
        st.subheader("Resultados")
        
        matches_data_input = []
        any_draw = False
        
        disabled_score = st.session_state.swiss_asking_penalties

        for i, match in enumerate(matches):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
            home_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['home'])
            away_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['away'])
            
            with c1: st.markdown(f"<h3 style='text-align: right'>{home_name}</h3>", unsafe_allow_html=True)
            
            # INPUTS NULOS (Vazios)
            with c2: 
                s1 = st.number_input("Gols", min_value=0, value=None, key=f"h_{round_idx}_{i}", disabled=disabled_score)
            with c3: 
                s2 = st.number_input("Gols", min_value=0, value=None, key=f"a_{round_idx}_{i}", disabled=disabled_score)
            
            with c4: st.markdown(f"<h3>{away_name}</h3>", unsafe_allow_html=True)
            
            pen_h = 0
            pen_a = 0
            
            if st.session_state.swiss_asking_penalties and s1 is not None and s2 is not None and s1 == s2:
                st.warning("⚠️ Empate! Decisão por pênaltis:")
                cp1, cp2 = st.columns(2)
                with cp1: pen_h = st.number_input(f"Pênaltis {home_name}", min_value=0, value=None, key=f"swiss_pen_h_{i}")
                with cp2: pen_a = st.number_input(f"Pênaltis {away_name}", min_value=0, value=None, key=f"swiss_pen_a_{i}")
                any_draw = True
            
            matches_data_input.append({
                'match_idx': i, 
                'home_id': match['home'], 'away_id': match['away'],
                'h_g': s1, 'a_g': s2,
                'h_p': pen_h, 'a_p': pen_a
            })
            
        btn_label = "Confirmar Classificação" if st.session_state.swiss_asking_penalties else "Conferir Resultados"
        submitted = st.form_submit_button(btn_label)
        
        if submitted:
            missing_input = False
            for m in matches_data_input:
                if m['h_g'] is None or m['a_g'] is None:
                    missing_input = True
            
            if missing_input:
                st.error("Por favor, preencha todos os placares do tempo normal.")
            else:
                has_new_draw = False
                
                if not st.session_state.swiss_asking_penalties:
                    for item in matches_data_input:
                        if item['h_g'] == item['a_g']:
                            has_new_draw = True
                    
                    if has_new_draw:
                        st.session_state.swiss_asking_penalties = True
                        st.rerun()
                    else:
                        if bye_team:
                            update_team_stats(bye_team['id'], 1, 0, is_winner=True, is_bye=True)
                        
                        for item in matches_data_input:
                            winner_is_home = item['h_g'] > item['a_g']
                            update_team_stats(item['home_id'], item['h_g'], item['a_g'], is_winner=winner_is_home)
                            update_team_stats(item['away_id'], item['a_g'], item['h_g'], is_winner=not winner_is_home)
                        
                        active_count = len([t for t in st.session_state.teams if t['status'] == 'Ativo'])
                        if active_count <= 1:
                            init_playoffs()
                        else:
                            generate_swiss_round()
                        st.rerun()
                
                else:
                    valid_penalties = True
                    for item in matches_data_input:
                        if item['h_g'] == item['a_g']:
                            if item['h_p'] is None or item['a_p'] is None:
                                st.error("Preencha os placares dos pênaltis nos jogos empatados.")
                                valid_penalties = False
                                break
                            if item['h_p'] == item['a_p']:
                                st.error("Pênaltis não podem terminar empatados!")
                                valid_penalties = False
                                break
                    
                    if valid_penalties:
                        if bye_team:
                            update_team_stats(bye_team['id'], 1, 0, is_winner=True, is_bye=True)

                        for item in matches_data_input:
                            hg, ag = item['h_g'], item['a_g']
                            hp, ap = item['h_p'], item['a_p']
                            
                            if hg != ag:
                                winner_is_home = hg > ag
                            else:
                                winner_is_home = hp > ap
                            
                            update_team_stats(item['home_id'], hg, ag, is_winner=winner_is_home)
                            update_team_stats(item['away_id'], ag, hg, is_winner=not winner_is_home)

                        active_count = len([t for t in st.session_state.teams if t['status'] == 'Ativo'])
                        if active_count <= 1:
                            init_playoffs()
                        else:
                            generate_swiss_round()
                        st.rerun()

elif st.session_state.phase == 'playoff_gameplay':
    st.title("🔥 Fase Final (Mata-Mata)")

    for idx, r_data in enumerate(st.session_state.playoff_schedule):
        if r_data['completed']:
            with st.expander(f"✅ {r_data['name']} (Concluído)", expanded=False):
                for m in r_data['matches']:
                    winner_name = "**" + (m['home']['name'] if m['winner_id'] == m['home']['id'] else m['away']['name']) + "**"
                    penalties_txt = f" (Pên: {m['h_pen']} x {m['a_pen']})" if m['is_penalties'] else ""
                    st.write(f"{m['label']}: {m['home']['name']} {m['h_goals']} x {m['a_goals']} {m['away']['name']}{penalties_txt} -> Vencedor: {winner_name}")

    current_round = st.session_state.playoff_schedule[-1]
    st.markdown(f"### ⚡ Em andamento: {current_round['name']}")
    
    if current_round['waiting']:
        names_waiting = ", ".join([t['name'] for t in current_round['waiting']])
        st.info(f"🛑 Times aguardando na próxima fase (Byes): **{names_waiting}**")
    
    with st.form(key=f"playoff_act_{len(st.session_state.playoff_schedule)}"):
        matches_data_input = []
        any_draw = False

        for i, match in enumerate(current_round['matches']):
            home = match['home']
            away = match['away']
            
            st.markdown(f"**{match['label']}**")
            
            col1, col2, col3, col4, col5 = st.columns([3, 1, 0.5, 1, 3])
            
            disabled_score = st.session_state.playoff_asking_penalties
            
            with col1: st.markdown(f"<h3 style='text-align: right'>{home['name']}</h3>", unsafe_allow_html=True)
            
            with col2: 
                val_h = st.number_input("Gols", min_value=0, value=None, key=f"pg_h_{i}", disabled=disabled_score)
            with col3: st.markdown("<h3 style='text-align: center'>X</h3>", unsafe_allow_html=True)
            with col4: 
                val_a = st.number_input("Gols", min_value=0, value=None, key=f"pg_a_{i}", disabled=disabled_score)
            with col5: st.markdown(f"<h3>{away['name']}</h3>", unsafe_allow_html=True)
            
            pen_h = 0
            pen_a = 0
            
            if st.session_state.playoff_asking_penalties and val_h is not None and val_a is not None and val_h == val_a:
                st.warning("⚠️ Empate! Insira os pênaltis:")
                cp1, cp2 = st.columns(2)
                with cp1: pen_h = st.number_input(f"Pênaltis {home['name']}", min_value=0, value=None, key=f"pen_h_{i}")
                with cp2: pen_a = st.number_input(f"Pênaltis {away['name']}", min_value=0, value=None, key=f"pen_a_{i}")
                any_draw = True
            
            matches_data_input.append({
                'match': match,
                'h_g': val_h, 'a_g': val_a,
                'h_p': pen_h, 'a_p': pen_a
            })

        btn_label = "Confirmar Classificação" if st.session_state.playoff_asking_penalties else "Conferir Resultados"
        submitted = st.form_submit_button(btn_label)
        
        if submitted:
            missing_input = False
            for m in matches_data_input:
                if m['h_g'] is None or m['a_g'] is None:
                    missing_input = True
            
            if missing_input:
                st.error("Por favor, preencha todos os placares do tempo normal.")
            
            else:
                has_new_draw = False
                winners = []
                
                if not st.session_state.playoff_asking_penalties:
                    for item in matches_data_input:
                        if item['h_g'] == item['a_g']:
                            has_new_draw = True
                    
                    if has_new_draw:
                        st.session_state.playoff_asking_penalties = True
                        st.rerun()
                    else:
                        for item in matches_data_input:
                            m = item['match']
                            m['h_goals'] = item['h_g']
                            m['a_goals'] = item['a_g']
                            m['is_penalties'] = False
                            m['h_pen'] = 0
                            m['a_pen'] = 0
                            w = m['home'] if item['h_g'] > item['a_g'] else m['away']
                            m['winner_id'] = w['id']
                            winners.append(w)
                        
                        current_round['completed'] = True
                        advance_playoff_round(winners, current_round['waiting'])
                        st.rerun()
                else:
                    valid_penalties = True
                    winners = []
                    for item in matches_data_input:
                        if item['h_g'] == item['a_g']:
                            if item['h_p'] is None or item['a_p'] is None:
                                st.error("Preencha os placares dos pênaltis.")
                                valid_penalties = False
                                break
                            if item['h_p'] == item['a_p']:
                                st.error("Pênaltis não podem terminar empatados!")
                                valid_penalties = False
                                break
                    
                    if valid_penalties:
                        for item in matches_data_input:
                            m = item['match']
                            m['h_goals'] = item['h_g']
                            m['a_goals'] = item['a_g']
                            m['h_pen'] = item['h_p']
                            m['a_pen'] = item['a_p']
                            
                            if item['h_g'] != item['a_g']:
                                m['is_penalties'] = False
                                w = m['home'] if item['h_g'] > item['a_g'] else m['away']
                            else:
                                m['is_penalties'] = True
                                w = m['home'] if item['h_p'] > item['a_p'] else m['away']
                            
                            m['winner_id'] = w['id']
                            winners.append(w)
                        
                        current_round['completed'] = True
                        advance_playoff_round(winners, current_round['waiting'])
                        st.rerun()

elif st.session_state.phase == 'champion':
    st.balloons()
    champ = st.session_state.champion
    
    st.markdown(f"""
    <div style="text-align: center; padding: 50px;">
        <h1>🏆 CAMPEÃO! 🏆</h1>
        <h2 style="color: gold; font-size: 80px;">{champ['name']}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### Trajetória do Campeão")
    st.write(f"Vitórias: {champ['wins']} | Derrotas: {champ['losses']}")
    
    if st.button("Reiniciar Torneio"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

render_sidebar_stats()
