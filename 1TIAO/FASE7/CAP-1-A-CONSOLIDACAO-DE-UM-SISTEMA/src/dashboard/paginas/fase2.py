"""Fase 2: leituras do ESP32, decisão da bomba e previsão de chuva."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.componentes import botao_servico, cabecalho, ler_csv, ler_json
from farmtech_core.config import SRC
from fase7_alertas_aws.lambda_alertas.regras_alerta import LIMITES, MOTIVOS

FIRMWARE = SRC / "fase2_iot_irrigacao" / "esp32" / "farmtech_irrigacao" / "farmtech_irrigacao.ino"
CENARIOS = {
    "realista": "Realista (P e K se esgotam e o pH cai)",
    "normal": "Normal (solo equilibrado)",
    "seca": "Seca (calor e falta de P/K)",
    "acidez": "Acidez (pH fora da faixa)",
    "saturacao": "Saturação (chuva intensa)",
}


def render() -> None:
    cabecalho("📡 Fase 2 — Sensores ESP32 e irrigação automática",
              "Botões NPK, LDR (pH), DHT22 (umidade/temperatura), relé da bomba e Open-Meteo")

    with st.container(border=True):
        a, b, c = st.columns([2, 1, 1])
        cenario = a.selectbox("Cenário do simulador", list(CENARIOS), format_func=CENARIOS.get)
        leituras = b.slider("Leituras (1 por hora)", 24, 168, 72, step=24)
        clima = c.checkbox("Chuva real (Open-Meteo)", value=False,
                           help="Usa a previsão real de Santa Maria-RS na última leitura")
        args = ["--leituras", str(leituras), "--cenario", cenario] + (["--clima"] if clima else [])
        botao_servico("fase2", args, "▶ Coletar leituras do ESP32", "f2_coletar")

    df = ler_csv("leituras")
    if df.empty:
        st.info("Ainda não há leituras: clique no botão acima.")
        return
    df["DATA_HORA"] = pd.to_datetime(df["DATA_HORA"])
    ultima = df.iloc[-1]
    st.caption(f"Origem dos dados: {ultima['ORIGEM']} · {len(df)} leituras")
    k = st.columns(5)
    k[0].metric("Umidade do solo", f"{ultima['UMIDADE_SOLO_PCT']:.1f} %")
    k[1].metric("pH do solo", f"{ultima['PH_SOLO']:.2f}")
    k[2].metric("Temperatura", f"{ultima['TEMPERATURA_C']:.1f} °C")
    k[3].metric("Chuva prevista", f"{ultima['CHUVA_PREVISTA_MM']:.1f} mm")
    k[4].metric("Bomba d'água", "LIGADA 💧" if ultima["BOMBA_LIGADA"] else "DESLIGADA")
    st.info(f"Decisão do firmware: **{MOTIVOS.get(ultima['MOTIVO_DECISAO'], ultima['MOTIVO_DECISAO'])}** · "
            f"N {'✅' if ultima['N_PRESENTE'] else '❌'} · P {'✅' if ultima['P_PRESENTE'] else '❌'} · "
            f"K {'✅' if ultima['K_PRESENTE'] else '❌'}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["DATA_HORA"], y=df["UMIDADE_SOLO_PCT"], name="Umidade do solo",
                             line=dict(color="#2563eb")))
    ligada = df[df["BOMBA_LIGADA"] == 1]
    fig.add_trace(go.Scatter(x=ligada["DATA_HORA"], y=ligada["UMIDADE_SOLO_PCT"], mode="markers",
                             name="Bomba ligada", marker=dict(color="#16a34a", size=9)))
    for valor, texto, cor in [(LIMITES["umidade_min"], "irrigar abaixo de 60%", "#d97706"),
                              (LIMITES["umidade_max"], "saturado acima de 80%", "#7c3aed"),
                              (LIMITES["umidade_critica"], "crítico 40%", "#b42318")]:
        fig.add_hline(y=valor, line_dash="dot", line_color=cor, annotation_text=texto)
    fig.update_layout(title="Umidade do solo e acionamento da bomba", height=360,
                      yaxis_title="%", margin=dict(t=50, b=20))
    st.plotly_chart(fig, width="stretch")

    esquerda, direita = st.columns(2)
    with esquerda:
        fig_ph = px.line(df, x="DATA_HORA", y="PH_SOLO", title="pH do solo (LDR)",
                         labels={"PH_SOLO": "pH", "DATA_HORA": ""})
        fig_ph.add_hrect(y0=LIMITES["ph_ideal_min"], y1=LIMITES["ph_ideal_max"],
                         fillcolor="#16a34a", opacity=0.12, line_width=0,
                         annotation_text="faixa ideal soja")
        st.plotly_chart(fig_ph, width="stretch")
    with direita:
        motivos = df["MOTIVO_DECISAO"].value_counts().reset_index()
        motivos.columns = ["Motivo", "Leituras"]
        st.plotly_chart(px.pie(motivos, names="Motivo", values="Leituras", hole=0.45,
                               title="Decisões do firmware"), width="stretch")

    npk = df[["DATA_HORA", "N_KGHA", "P_KGHA", "K_KGHA"]].melt("DATA_HORA", var_name="Nutriente",
                                                               value_name="kg/ha")
    st.plotly_chart(px.line(npk, x="DATA_HORA", y="kg/ha", color="Nutriente",
                            title="Nutrientes no solo (botões N, P e K)"), width="stretch")

    clima = ler_json("clima")
    with st.expander("Previsão Open-Meteo (Santa Maria-RS)"):
        if clima:
            st.write(f"Consulta em {clima['consultado_em']}: {clima['chuva_24h_mm']} mm nas próximas 24 h")
            st.bar_chart(pd.DataFrame({"chuva (mm)": clima["chuva_mm"]},
                                      index=pd.to_datetime(clima["horas"])))
        else:
            st.write("Marque “Chuva real (Open-Meteo)” e colete as leituras.")
    with st.expander("Firmware do ESP32 (C/C++) e circuito Wokwi"):
        st.markdown("Cole o código e o `diagram.json` em [wokwi.com](https://wokwi.com) "
                    "(ESP32 DevKit V1) ou rode no Wokwi for VS Code e leia a Serial com "
                    "`python farmtech.py fase2 --serial rfc2217://localhost:4000`.")
        st.code(FIRMWARE.read_text(encoding="utf-8"), language="cpp")
    st.dataframe(df.tail(24), hide_index=True, width="stretch")
