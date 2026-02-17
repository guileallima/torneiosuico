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
if 'asking_penalties' not in st.session_state:
    st.session_state.asking_penalties = False 

# --- FUNÇÕES AUXILIARES ---

def get_sorted_rankings(teams, for_pairing=False):
    # REGRA: Vitórias > Bye (False > True) > Saldo > Gols Pró
    # Se for para pareamento, embaralhamos antes para que empates não sigam ordem alfabética/cadastro
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

def render_sidebar_stats():
    """Função para mostrar o histórico na barra lateral"""
    with st.sidebar:
        st.header("📊 Classificação / Histórico")
        if st.session_state.teams:
            # Mostra ranking oficial (sem aleatoriedade, apenas mérito)
            sorted_teams = get_sorted_rankings(st.session_state.teams, for_pairing=False)
            
            display_data = []
            for t in sorted_teams:
                record = f"{t['wins']}-{t['losses']}"
                display_data.append({
                    'Time': t['name'],
                    'Rec': record,
                    'Status': t['status'],
                    'Bye': 'Sim' if t['received_bye'] else '-'
                })
            
            df = pd.DataFrame(display_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.info("Critérios: Vitórias > Sem Bye > Saldo > Gols Pró")

# --- LÓGICA DO SUIÇO ---

def generate_swiss_round():
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    
    # --- CORREÇÃO DO SORTEIO ---
    # Embaralhamos a lista de ativos ANTES de qualquer lógica.
    # Isso garante que na Rodada 1 (onde todos são iguais), o Bye e os pares sejam aleatórios.
    random.shuffle(active_teams)
    
    # REGRA: BYE (NÚMERO ÍMPAR)
    bye_team = None
    if len(active_teams) % 2 != 0:
        # Ordena do pior para o melhor para achar o candidato ao bye
        # Como já demos shuffle antes, se houver empate de stats, a ordem é aleatória
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
    # Usamos for_pairing=True para garantir aleatoriedade nos empates de pareamento também
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

    if num_q == 4:
        round_name = "Semifinais"
        current_matches = [
            {'id': 'S1', 'home': seeds[0], 'away': seeds[3], 'label': 'Semi 1'},
            {'id': 'S2', 'home': seeds[1], 'away': seeds[2], 'label': 'Semi 2'}
        ]
    elif num_q == 5:
        round_name = "Wildcard (Repescagem)"
        waiting_teams = [seeds[0], seeds[1], seeds[2]] 
        current_matches = [
            {'id': 'WC', 'home': seeds[3], 'away': seeds[4], 'label': 'Repescagem'}
        ]
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
    st.session_state.asking_penalties = False

def advance_playoff_round(results, waiting_teams):
    st.session_state.asking_penalties = False 
    
    pool = waiting_teams + results
    count = len(pool)
    
    next_matches = []
    next_round_name = ""
    
    if count == 2:
        next_round_name = "Grande Final"
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

# 1. Callback para limpar o input de texto
def add_team_callback():
    # Pega o valor digitado na chave 'team_input'
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
        # LIMPA A CAIXA DE TEXTO
        st.session_state.team_input = "" 
    elif not new_team:
        st.warning("Digite um nome.")
    else:
        st.error("Time já existe.")

if st.session_state.phase == 'registration':
    st.title("🏆 Inscrição de Times")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        # CORREÇÃO DA LIMPEZA: Usamos key="team_input"
        st.text_input("Nome do Time", key="team_input")
    with col2:
        # O botão chama a função add_team_callback antes de recarregar
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

    with st.form(key=f"round_form_{round_idx}"):
        st.subheader("Resultados")
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
                init_playoffs()
                st.rerun()
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
            
            disabled_score = st.session_state.asking_penalties
            
            with col1: st.markdown(f"<h3 style='text-align: right'>{home['name']}</h3>", unsafe_allow_html=True)
            with col2: 
                val_h = st.number_input("Gols", min_value=0, key=f"pg_h_{i}", disabled=disabled_score)
            with col3: st.markdown("<h3 style='text-align: center'>X</h3>", unsafe_allow_html=True)
            with col4: 
                val_a = st.number_input("Gols", min_value=0, key=f"pg_a_{i}", disabled=disabled_score)
            with col5: st.markdown(f"<h3>{away['name']}</h3>", unsafe_allow_html=True)
            
            pen_h = 0
            pen_a = 0
            
            if st.session_state.asking_penalties and val_h == val_a:
                st.warning("⚠️ Empate! Insira os pênaltis:")
                cp1, cp2 = st.columns(2)
                with cp1: pen_h = st.number_input(f"Pênaltis {home['name']}", min_value=0, key=f"pen_h_{i}")
                with cp2: pen_a = st.number_input(f"Pênaltis {away['name']}", min_value=0, key=f"pen_a_{i}")
                any_draw = True
            
            matches_data_input.append({
                'match': match,
                'h_g': val_h, 'a_g': val_a,
                'h_p': pen_h, 'a_p': pen_a
            })

        btn_label = "Confirmar Classificação" if st.session_state.asking_penalties else "Conferir Resultados"
        submitted = st.form_submit_button(btn_label)
        
        if submitted:
            has_new_draw = False
            winners = []
            
            if not st.session_state.asking_penalties:
                for item in matches_data_input:
                    if item['h_g'] == item['a_g']:
                        has_new_draw = True
                
                if has_new_draw:
                    st.session_state.asking_penalties = True
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

# RENDERIZA A SIDEBAR NO FINAL PARA GARANTIR ATUALIZAÇÃO
render_sidebar_stats()
