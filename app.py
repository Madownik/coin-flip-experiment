import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import qrcode
import io
import time

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Eksperyment: Biased Coin Flip", layout="wide")

# --- GLOBALNY MAGAZYN DANYCH ---
@st.cache_resource
def get_global_store():
    return {
        "players": {},            # {nazwa_gracza: procent_kapitatu}
        "simulation_started": False
    }

global_store = get_global_store()

# Pobranie trybu z URL (?role=player lub domyślnie host)
role = st.query_params.get("role", "host")

# --- WIDOK 1: TELEFON UCZESTNIKA (?role=player) ---
if role == "player":
    st.title("🎲 Dołącz do eksperymentu")
    st.write("Startujesz z kapitałem **100 $**. Wykonamy 100 rzutów monetą z szansą wygranej **60%**.")

    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False

    if not st.session_state["submitted"]:
        with st.form("player_form"):
            player_name = st.text_input("Twoje Imię / Nick:", value="")
            bet_pct = st.slider("Jaki % AKTUALNEGO kapitału stawiasz w każdym rzucie?",
                                min_value=1, max_value=100, value=50, step=1)
            submitted = st.form_submit_button("Zatwierdź strategię")

            if submitted:
                name_clean = player_name.strip()
                if name_clean != "":
                    global_store["players"][name_clean] = bet_pct / 100.0
                    st.session_state["submitted"] = True
                    st.session_state["my_name"] = name_clean
                    st.session_state["my_bet"] = bet_pct
                    st.rerun()
                else:
                    st.error("Proszę podać imię.")
    else:
        st.success(f"Witaj **{st.session_state['my_name']}**! Twoja strategia ({st.session_state['my_bet']}% kapitału) została zapisana.")
        st.info("Spójrz na ekran główny. Czekamy na rozpoczęcie symulacji przez prowadzącego.")

# --- WIDOK 2: EKRAN GŁÓWNY PREZENTERA ---
else:
    st.title("📊 Eksperyment Decyzyjny: Symulacja Rzutu Monetą (60/40)")

    # Przycisk resetu w prawym górnym rogu
    top_col1, top_col2 = st.columns([4, 1])
    with top_col2:
        if st.button("🧹 Resetuj wszystko (Nowi gracze)", use_container_width=True):
            global_store["players"] = {}
            global_store["simulation_started"] = False
            st.rerun()

    # Krok A: Połączenia i QR kod
    if not global_store["simulation_started"]:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("1. Zeskanuj QR i dołącz")
            base_url = st.query_params.get("server_url", "http://localhost:8501")
            player_url = f"{base_url}/?role=player"

            qr = qrcode.make(player_url)
            buf = io.BytesIO()
            qr.save(buf)
            st.image(buf.getvalue(), width=250)
            st.caption(f"Link dla graczy: `{player_url}`")

        with col2:
            current_players = global_store["players"]
            st.subheader(f"2. Zarejestrowani gracze ({len(current_players)})")
            
            if current_players:
                players_df = pd.DataFrame(
                    list(current_players.items()),
                    columns=["Gracz", "Stawiany % Kapitału"]
                )
                players_df["Stawiany % Kapitału"] = (players_df["Stawiany % Kapitału"] * 100).astype(int).astype(str) + "%"
                st.dataframe(players_df, height=250, use_container_width=True)
            else:
                st.info("Czekanie na pierwszych graczy...")

            if len(current_players) > 0:
                if st.button("🚀 ROZPOCZNIJ SYMULACJĘ (100 RZUTÓW)", type="primary"):
                    global_store["simulation_started"] = True
                    st.rerun()

        time.sleep(2)
        st.rerun()

    # Krok B: Symulacja na żywo i wykresy
    else:
        st.subheader("📈 Przebieg symulacji w czasie rzeczywistym")

        num_flips = 100
        players = global_store["players"]
        player_names = list(players.keys())
        percentages = np.array([players[p] for p in player_names])

        history = np.zeros((num_flips + 1, len(player_names)))
        history[0, :] = 100.0

        # W PEŁNI LOSOWE RZUTY
        outcomes = np.random.choice([1, -1], size=num_flips, p=[0.60, 0.40])

        plot_spot = st.empty()
        stats_spot = st.empty()

        for t in range(1, num_flips + 1):
            outcome = outcomes[t - 1]
            prev_capital = history[t - 1, :]
            bet_amounts = prev_capital * percentages

            if outcome == 1:
                history[t, :] = prev_capital + bet_amounts
            else:
                history[t, :] = np.maximum(0, prev_capital - bet_amounts)

            current_history = history[:t+1, :]
            means = np.mean(current_history, axis=1)
            medians = np.median(current_history, axis=1)

            fig = go.Figure()

            for i, p_name in enumerate(player_names):
                fig.add_trace(go.Scatter(
                    y=current_history[:, i],
                    mode='lines',
                    line=dict(width=1, color='rgba(150, 150, 150, 0.3)'),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            fig.add_trace(go.Scatter(
                y=means, mode='lines', name='ŚREDNIA', line=dict(color='blue', width=4)
            ))

            fig.add_trace(go.Scatter(
                y=medians, mode='lines', name='MEDIANA', line=dict(color='red', width=4)
            ))

            fig.update_layout(
                title=f"Rzut {t}/{num_flips} | Ostatni wynik: {'WYGRANA' if outcome == 1 else 'PRZEGRANA'}",
                xaxis_title="Numer Rzutu",
                yaxis_title="Kapitał ($)",
                yaxis_type="log",
                template="plotly_white",
                height=450
            )

            plot_spot.plotly_chart(fig, use_container_width=True)

            with stats_spot.container():
                m1, m2, m3 = st.columns(3)
                m1.metric("Średni kapitał sali", f"{means[-1]:.2f} $")
                m2.metric("Mediana kapitału sali", f"{medians[-1]:.2f} $")
                m3.metric("Liczba bankructw (<1 $)", f"{np.sum(current_history[-1, :] < 1)}")

            time.sleep(0.05)

        # Krok C: Wykres końcowy po 100 rzutach
        st.subheader("📊 Finalne wyniki uczestników")
        final_balances = history[-1, :]

        final_df = pd.DataFrame({
            "Gracz": player_names,
            "Procent Betu": [f"{p*100:.0f}%" for p in percentages],
            "Finalny Stan Konta ($)": np.round(final_balances, 2)
        }).sort_values(by="Finalny Stan Konta ($)", ascending=False)

        fig_bar = go.Figure(go.Bar(
            x=final_df["Gracz"],
            y=final_df["Finalny Stan Konta ($)"],
            text=final_df["Procent Betu"],
            textposition='auto'
        ))
        fig_bar.update_layout(
            title="Koniec symulacji — Zestawienie końcowych kapitałów",
            xaxis_title="Gracz",
            yaxis_title="Kapitał ($)",
            template="plotly_white"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(final_df, use_container_width=True)

        # --- TABELA HISTORII DLA ZWYCIĘZCY ---
        winner_name = final_df.iloc[0]["Gracz"]
        winner_idx = player_names.index(winner_name)
        winner_pct = percentages[winner_idx]

        st.subheader(f"🏆 Historia rzutów dla zwycięzcy: {winner_name} (Stawka: {winner_pct*100:.0f}%)")
        
        winner_rows = []
        for r in range(1, num_flips + 1):
            start_cap = history[r-1, winner_idx]
            bet_val = start_cap * winner_pct
            res = outcomes[r-1]
            end_cap = history[r, winner_idx]
            
            winner_rows.append({
                "Rzut #": r,
                "Kapitał Początkowy ($)": round(start_cap, 2),
                "Wartość Obstawienia ($)": round(bet_val, 2),
                "Wynik Rzutu": "WYGRANA (+)" if res == 1 else "PRZEGRANA (-)",
                "Kapitał Po Rzucie ($)": round(end_cap, 2)
            })

        winner_history_df = pd.DataFrame(winner_rows)
        
        with st.expander(f"🔍 Kliknij, aby zobaczyć pełną historię 100 rzutów gracza {winner_name}"):
            st.dataframe(winner_history_df, use_container_width=True, height=400)

        # --- AKCJE PO ZAKOŃCZENIU SYMULACJI ---
        st.markdown("---")
        c1, c2 = st.columns(2)
        
        with c1:
            if st.button("🎲 Ponów rzuty dla TYCH SAMYCH graczy", type="primary", use_container_width=True):
                st.rerun()

        with c2:
            if st.button("🧹 Resetuj wszystko (Nowy eksperyment)", use_container_width=True):
                global_store["players"] = {}
                global_store["simulation_started"] = False
                st.rerun()
