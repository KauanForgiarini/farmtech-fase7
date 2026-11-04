"""Fase 4: modelos de regressão (irrigação, adubação, rendimento) e previsão interativa."""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.componentes import botao_servico, cabecalho, ler_csv
from farmtech_core.config import PASTA_MODELOS_ML
from fase4_modelos_preditivos.treinar_modelos import carregar_modelos, prever
from fase7_alertas_aws.lambda_alertas.regras_alerta import LIMITES

NOMES = {"VOLUME_IRRIGACAO_L": ("Volume de irrigação", "L/m²"),
         "NECESSIDADE_FERT_KGHA": ("Fertilização necessária", "kg/ha"),
         "RENDIMENTO_ESPERADO_SCHA": ("Rendimento esperado", "sc/ha")}


@st.cache_resource(show_spinner=False)
def modelos_em_cache(_marca: float):
    return carregar_modelos()


def recomendacoes(umidade, ph, chuva, volume, fert, rendimento) -> list[str]:
    acoes = []
    if chuva >= LIMITES["chuva_limiar_mm"]:
        acoes.append("🌧️ Chuva prevista: **não irrigar** (economia de água).")
    elif umidade < LIMITES["umidade_min"]:
        acoes.append(f"💧 Irrigar cerca de **{volume:.2f} L/m²** para atingir 70% de umidade.")
    else:
        acoes.append("✅ Umidade adequada: irrigação desnecessária agora.")
    if ph < LIMITES["ph_ideal_min"]:
        acoes.append(f"⚠️ pH {ph:.1f} ácido: calagem com calcário dolomítico.")
    elif ph > LIMITES["ph_ideal_max"]:
        acoes.append(f"⚠️ pH {ph:.1f} alcalino: enxofre elementar/gesso.")
    acoes.append(f"🌿 Fertilização sugerida: **{fert:.1f} kg/ha**.")
    acoes.append(f"📈 Rendimento estimado: **{rendimento:.1f} sc/ha** (média regional 55 sc/ha).")
    return acoes


def render() -> None:
    cabecalho("🔮 Fase 4 — Assistente agrícola com Machine Learning",
              "Regressão Scikit-Learn (Linear, Ridge, Random Forest, Gradient Boosting) com CV 5-fold")

    meta_arquivo = PASTA_MODELOS_ML / "metadata.json"
    esquerda, direita = st.columns([2, 3])
    with esquerda:
        botao_servico("fase4", rotulo="▶ Treinar modelos e prever leituras atuais")
    if not meta_arquivo.exists():
        st.info("Treine os modelos com o botão acima.")
        return
    meta = json.loads(meta_arquivo.read_text(encoding="utf-8"))
    with direita:
        linhas = []
        for alvo, info in meta["resultados"].items():
            for modelo, m in info["modelos"].items():
                linhas.append({"Alvo": NOMES[info["coluna"]][0], "Modelo": modelo,
                               "MAE": m["MAE"], "RMSE": m["RMSE"], "R²": m["R2"],
                               "CV-R²": m["CV_R2_media"],
                               "Escolhido": "⭐" if modelo == info["melhor_modelo"] else ""})
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", height=300)

    st.subheader("Previsão em tempo real")
    modelos = modelos_em_cache(meta_arquivo.stat().st_mtime)
    leituras = ler_csv("leituras")
    base = leituras.iloc[-1] if not leituras.empty else None
    controles = [("UMIDADE_SOLO_PCT", "Umidade %", 15.0, 95.0, 52.0),
                 ("PH_SOLO", "pH", 4.0, 8.5, 6.2), ("TEMPERATURA_C", "Temp. °C", 5.0, 45.0, 27.0),
                 ("CHUVA_PREVISTA_MM", "Chuva mm", 0.0, 40.0, 0.0),
                 ("N_KGHA", "N kg/ha", 20.0, 140.0, 80.0), ("P_KGHA", "P kg/ha", 20.0, 110.0, 60.0),
                 ("K_KGHA", "K kg/ha", 20.0, 120.0, 75.0)]
    valores = {}
    for coluna, (campo, rotulo, minimo, maximo, padrao) in zip(st.columns(7), controles):
        inicial = float(base[campo]) if base is not None else padrao
        valores[campo] = coluna.slider(rotulo, minimo, maximo, min(maximo, max(minimo, inicial)))
    entrada = pd.DataFrame([valores])
    st.caption("Os controles começam com a última leitura do ESP32 (Fase 2).")
    try:
        resultado = prever(modelos, entrada).iloc[0]
    except Exception as erro:
        st.error(f"Modelos incompatíveis com esta versão do scikit-learn ({erro}). Treine novamente.")
        return
    for coluna, (alvo, (nome, unidade)) in zip(st.columns(3), NOMES.items()):
        coluna.metric(nome, f"{resultado[alvo]:.2f} {unidade}")
    for acao in recomendacoes(entrada["UMIDADE_SOLO_PCT"][0], entrada["PH_SOLO"][0],
                              entrada["CHUVA_PREVISTA_MM"][0], resultado["VOLUME_IRRIGACAO_L"],
                              resultado["NECESSIDADE_FERT_KGHA"], resultado["RENDIMENTO_ESPERADO_SCHA"]):
        st.markdown(f"- {acao}")

    previsoes = ler_csv("previsoes")
    if not previsoes.empty and not leituras.empty:
        serie = leituras.merge(previsoes, on="ID_LEITURA")
        serie["DATA_HORA"] = pd.to_datetime(serie["DATA_HORA"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=serie["DATA_HORA"], y=serie["VOLUME_IRRIGACAO_L"],
                                 name="Volume previsto (L/m²)", line=dict(color="#2563eb")))
        fig.add_trace(go.Bar(x=serie["DATA_HORA"], y=serie["BOMBA_LIGADA"], name="Bomba ligada",
                             marker_color="#16a34a", opacity=0.35, yaxis="y2"))
        fig.update_layout(title="Previsão do modelo para cada leitura do ESP32", height=340,
                          yaxis2=dict(overlaying="y", side="right", range=[0, 1.2], showgrid=False,
                                      title="bomba"), margin=dict(t=50, b=20))
        st.plotly_chart(fig, width="stretch")

    info = meta["resultados"]["volume_irrigacao"]
    if info.get("importancia_features"):
        imp = pd.DataFrame(info["importancia_features"].items(), columns=["Variável", "Importância"])
        st.plotly_chart(px.bar(imp.sort_values("Importância"), x="Importância", y="Variável",
                               orientation="h", title=f"Importância das variáveis ({info['melhor_modelo']}"
                               " · volume de irrigação)"), width="stretch")
