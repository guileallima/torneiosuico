import streamlit as st
import pandas as pd
import random
import math

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor de Torneio Suíço", layout="wide")

# --- ESTRUTURA DE DADOS (MODELO) ---
# Usaremos st.session_state para persistir os dados enquanto não temos banco de dados.
if 'teams' not in st.session_state:
    st.session_state.teams = []  # Lista de dicionários
if 'rounds' not in st.session_state:
    st.session_state.rounds = [] # Histórico de rodadas
if 'phase' not in st.session_state:
    st.session_state.phase = 'registration' # registration, swiss, playoff
if 'playoff_matches' not in st.session_state:
    st.session_state.playoff_matches = []

# --- FUNÇÕES AUXILIARES DE LÓGICA ---

def get_sorted_rankings(teams, for_pairing=False):
    # REGRA: Ordem de prioridade: Vitórias > Bye (Não ter é melhor) > Saldo > Gols Pró > Sorteio
    # Nota: No python, sort é estável. Para random, embaralhamos antes.
    
    # Se for para pareamento, o sorteio é aleatório. Se for ranking final, precisa ser determinístico (opcional)
    if for_pairing:
        random.shuffle(teams)
    
    return sorted(teams, key=lambda x: (
        x['wins'], 
        not x['received_bye'], # True (não recebeu) > False (recebeu) -> Python trata True como 1, False como 0
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
            
            # ATUALIZAÇÃO DE STATUS (TRIPLE ELIMINATION)
            if team['wins'] >= 3:
                team['status'] = 'Classificado'
            elif team['losses'] >= 3:
                team['status'] = 'Eliminado'
            break

def generate_swiss_round():
    active_teams = [t for t in st.session_state.teams if t['status'] == 'Ativo']
    
    # REGRA: BYE (NÚMERO ÍMPAR)
    # O time com pior campanha que AINDA NÃO recebeu bye ganha.
    bye_team = None
    if len(active_teams) % 2 != 0:
        # Ordena do pior para o melhor para achar o candidato ao bye
        # Critério reverso: Menos vitórias, Já teve bye (falso), pior saldo
        worst_sorted = sorted(active_teams, key=lambda x: (
            x['wins'], 
            not x['received_bye'], 
            x['goal_diff']
        ))
        
        # Procura o primeiro que não teve bye
        for t in worst_sorted:
            if not t['received_bye']:
                bye_team = t
                break
        
        # Se todos já tiveram (caso raro), pega o pior absoluto
        if not bye_team:
            bye_team = worst_sorted[0]
            
        active_teams.remove(bye_team)

    # AGRUPAMENTO E PAREAMENTO (Simplificado para Greedy Pairing)
    # Ordena os ativos por força
    ranked_pool = get_sorted_rankings(active_teams, for_pairing=True)
    matches = []
    
    while len(ranked_pool) >= 2:
        home = ranked_pool.pop(0)
        # Tenta achar um oponente que ainda não enfrentou
        opponent = None
        for i, candidate in enumerate(ranked_pool):
            if candidate['id'] not in home['history']:
                opponent = ranked_pool.pop(i)
                break
        
        # Se não achar inédito (final de torneio), pega o próximo melhor (Regra de Exceção)
        if not opponent:
            opponent = ranked_pool.pop(0)
            
        matches.append({
            'home': home['id'], 'away': opponent['id'], 
            'home_score': 0, 'away_score': 0, 'completed': False
        })
        
        # Registra histórico
        home['history'].append(opponent['id'])
        opponent['history'].append(home['id'])

    # Salva a rodada
    round_data = {'matches': matches, 'bye': bye_team}
    st.session_state.rounds.append(round_data)

def generate_playoffs():
    # REGRA: Classificação por Mérito para Seeds
    qualified = [t for t in st.session_state.teams if t['status'] == 'Classificado']
    seeds = get_sorted_rankings(qualified) # Já aplica a regra de "Quem não teve bye fica na frente"
    
    num_q = len(seeds)
    matchups = []
    
    st.write(f"Classificados: {num_q} times.")
    
    # LÓGICA DINÂMICA (CASOS A, B, C, D, E)
    if num_q == 4:
        matchups = [
            {'round': 'Semi 1', 'home': seeds[0], 'away': seeds[3]}, # 1 vs 4
            {'round': 'Semi 2', 'home': seeds[1], 'away': seeds[2]}  # 2 vs 3
        ]
    elif num_q == 5:
        matchups = [
            {'round': 'Wildcard', 'home': seeds[3], 'away': seeds[4]}, # 4 vs 5
            {'round': 'Semi 1', 'home': seeds[0], 'away': 'Vencedor Wildcard'}, # 1 espera
            {'round': 'Semi 2', 'home': seeds[1], 'away': seeds[2]}
        ]
    elif num_q == 6:
        matchups = [
            {'round': 'Quartas A', 'home': seeds[3], 'away': seeds[4]}, # 4 vs 5
            {'round': 'Quartas B', 'home': seeds[2], 'away': seeds[5]}, # 3 vs 6
            {'round': 'Semi 1', 'home': seeds[0], 'away': 'Venc. Quartas A'}, # 1 espera (Melhor pega pior seed teórica)
            {'round': 'Semi 2', 'home': seeds[1], 'away': 'Venc. Quartas B'}  # 2 espera
        ]
    elif num_q == 7:
        matchups = [
            {'round': 'Quartas A', 'home': seeds[3], 'away': seeds[4]},
            {'round': 'Quartas B', 'home': seeds[2], 'away': seeds[5]},
            {'round': 'Quartas C', 'home': seeds[1], 'away': seeds[6]},
            {'round': 'Semi 1', 'home': seeds[0], 'away': 'Venc. Quartas A'}, # Só o 1 espera
            {'round': 'Semi 2', 'home': 'Venc. Qurtas C', 'away': 'Venc. Quartas B'}
        ]
    elif num_q >= 8: # Corta para 8 se tiver mais
        seeds = seeds[:8]
        matchups = [
            {'round': 'Quartas 1', 'home': seeds[0], 'away': seeds[7]}, # 1 vs 8
            {'round': 'Quartas 2', 'home': seeds[1], 'away': seeds[6]}, # 2 vs 7
            {'round': 'Quartas 3', 'home': seeds[2], 'away': seeds[5]}, # 3 vs 6
            {'round': 'Quartas 4', 'home': seeds[3], 'away': seeds[4]}  # 4 vs 5
        ]
    
    st.session_state.playoff_matches = matchups
    st.session_state.phase = 'playoff'

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
                # MODELO DE DADOS DO TIME
                t_obj = {
                    'id': len(st.session_state.teams) + 1,
                    'name': new_team,
                    'wins': 0, 'losses': 0,
                    'goals_for': 0, 'goal_diff': 0,
                    'received_bye': False,
                    'history': [], # IDs dos oponentes enfrentados
                    'status': 'Ativo' # Ativo, Classificado, Eliminado
                }
                st.session_state.teams.append(t_obj)
                st.success(f"{new_team} adicionado!")
            elif not new_team:
                st.warning("Digite um nome.")
            else:
                st.error("Time já existe.")

    # Listar Times
    if st.session_state.teams:
        df_teams = pd.DataFrame(st.session_state.teams)
        st.dataframe(df_teams[['name', 'status']], use_container_width=True)
    
    st.markdown("---")
    if st.button("Iniciar Torneio"):
        qtd = len(st.session_state.teams)
        if 6 <= qtd <= 16:
            st.session_state.phase = 'swiss'
            generate_swiss_round() # Gera a primeira rodada
            st.rerun()
        else:
            st.error(f"É necessário entre 6 e 16 times. Atual: {qtd}")

# --- FASE 2: SUÍÇO ---
elif st.session_state.phase == 'swiss':
    st.header(f"Fase Suíça - Rodada {len(st.session_state.rounds)}")
    
    current_round = st.session_state.rounds[-1]
    matches = current_round['matches']
    bye_team = current_round['bye']
    
    if bye_team:
        st.info(f"🎉 BYE: O time **{bye_team['name']}** folga nesta rodada e ganha +1 Vitória.")

    with st.form("results_form"):
        st.subheader("Resultados dos Jogos")
        
        results = []
        for i, match in enumerate(matches):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
            
            # Buscar nomes
            home_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['home'])
            away_name = next(t['name'] for t in st.session_state.teams if t['id'] == match['away'])
            
            with c1: st.markdown(f"<h3 style='text-align: right'>{home_name}</h3>", unsafe_allow_html=True)
            with c2: s1 = st.number_input("Gols", min_value=0, key=f"h_{i}")
            with c3: s2 = st.number_input("Gols", min_value=0, key=f"a_{i}")
            with c4: st.markdown(f"<h3>{away_name}</h3>", unsafe_allow_html=True)
            
            results.append({'match_idx': i, 'h_score': s1, 'a_score': s2})
            
        submitted = st.form_submit_button("Confirmar Resultados e Encerrar Rodada")
        
        if submitted:
            # 1. Processar Bye
            if bye_team:
                update_team_stats(bye_team['id'], 1, 0, is_bye=True)
            
            # 2. Processar Jogos
            for res in results:
                m = matches[res['match_idx']]
                h_goals = res['h_score']
                a_goals = res['a_score']
                
                # Atualizar Stats
                update_team_stats(m['home'], h_goals, a_goals)
                update_team_stats(m['away'], a_goals, h_goals)
            
            # 3. Verificar se a Fase Suíça acabou
            active_count = len([t for t in st.session_state.teams if t['status'] == 'Ativo'])
            
            if active_count <= 1: # Se sobrar 0 ou 1, acabou
                generate_playoffs()
            else:
                generate_swiss_round()
            
            st.rerun()

    # Tabela de Classificação Atualizada
    st.markdown("### Classificação Atual")
    sorted_teams = get_sorted_rankings(st.session_state.teams)
    
    # Prepara dataframe bonito
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

# --- FASE 3: MATA-MATA ---
elif st.session_state.phase == 'playoff':
    st.header("🔥 Fase Final (Mata-Mata)")
    st.balloons()
    
    st.markdown("### Chaveamento Gerado (Baseado no Mérito)")
    
    for match in st.session_state.playoff_matches:
        home_name = match['home']['name'] if isinstance(match['home'], dict) else match['home']
        away_name = match['away']['name'] if isinstance(match['away'], dict) else match['away']
        
        st.info(f"**{match['round']}**: {home_name} vs {away_name}")
        
    st.markdown("---")
    st.warning("O torneio foi gerado! Para salvar em banco de dados no futuro, basta exportar o 'st.session_state.teams' e 'rounds'.")

    if st.button("Reiniciar Torneio"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()