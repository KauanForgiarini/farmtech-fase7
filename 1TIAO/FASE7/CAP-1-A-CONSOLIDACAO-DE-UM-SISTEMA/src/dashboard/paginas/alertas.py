"""Fase 7: serviço de alertas na AWS (S3 -> Lambda -> SNS) com ações corretivas."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.componentes import (banco_pronto, botao_servico, cabecalho, cartao_alerta,
                                   consultar)
from fase7_alertas_aws import aws_config
from fase7_alertas_aws.lambda_alertas import regras_alerta as regras
from fase7_alertas_aws.publicar_alerta import coletar_dados

MODOS = {
    "auto": "Automático (Lambda se a AWS estiver configurada)",
    "s3": "S3 → gatilho → Lambda → SNS (orientado a eventos)",
    "lambda": "Invocar a Lambda diretamente",
    "sns": "Publicar direto no tópico SNS",
    "local": "Somente simular (sem AWS)",
}


def render() -> None:
    cabecalho("🚨 Fase 7 — Serviço de alertas na AWS",
              "Monitora sensores (Fases 1/2) e visão computacional (Fase 6) e avisa os "
              "funcionários por e-mail/SMS com ações corretivas")

    config = aws_config.carregar()
    implantado = bool(config.get("topic_arn"))
    st.caption("Recursos AWS: " + (f"tópico `{config['topic_arn']}` · Lambda "
                                    f"`{config['funcao_lambda']}` · bucket `{config['bucket']}`"
                                    if implantado else
                                    "ainda não implantados (página Fase 5 ou "
                                    "`python farmtech.py aws-deploy --email ...`)"))

    esquerda, direita = st.columns([3, 2])
    with esquerda:
        st.subheader("Avaliação atual das regras")
        ultimas = st.slider("Leituras recentes avaliadas", 1, 24, 6)
        leituras, deteccoes, fonte = coletar_dados(ultimas)
        alertas = regras.avaliar_payload({"leituras": leituras, "deteccoes": deteccoes},
                                         ultimas_leituras=ultimas)
        st.caption(f"Fonte: {fonte} · {len(leituras)} leituras · {len(deteccoes)} detecções · "
                   f"{len(alertas)} alertas")
        if not alertas:
            st.success("Nenhuma ação corretiva necessária no momento.")
        for alerta in alertas:
            cartao_alerta(alerta)
    with direita:
        st.subheader("Enviar aos funcionários")
        modo = st.selectbox("Canal", list(MODOS), format_func=MODOS.get)
        origem = st.radio("Dados", ["todos", "sensores", "visao"], horizontal=True)
        minima = st.select_slider("Severidade mínima", regras.SEVERIDADES, value="MEDIO")
        teste = st.checkbox("Enviar leitura de teste crítica (demonstração)")
        args = ["--modo", modo, "--origem", origem, "--ultimas", str(ultimas),
                "--severidade-minima", minima] + (["--teste-critico"] if teste else [])
        botao_servico("alertas", args, "▶ Disparar serviço de alertas", "f7_enviar")
        if alertas:
            mensagem = regras.montar_mensagem(regras.filtrar_severidade(alertas, minima))
            with st.expander("Prévia do e-mail e do SMS"):
                st.markdown(f"**Assunto:** {mensagem['assunto']}")
                st.code(mensagem["corpo"], language="text")
                st.markdown(f"**SMS:** {mensagem['sms']}")

    if banco_pronto():
        historico = consultar("SELECT * FROM ALERTA ORDER BY ID_ALERTA DESC")
        if not historico.empty:
            st.subheader("Histórico de alertas (tabela ALERTA da Fase 3)")
            resumo = historico.groupby(["SEVERIDADE", "STATUS_ENVIO"]).size().reset_index(name="ALERTAS")
            a, b = st.columns([2, 3])
            a.plotly_chart(px.bar(resumo, x="SEVERIDADE", y="ALERTAS", color="STATUS_ENVIO",
                                  category_orders={"SEVERIDADE": regras.SEVERIDADES[::-1]}),
                           width="stretch")
            b.dataframe(historico[["DATA_HORA", "SEVERIDADE", "TITULO", "LOCAL_ALERTA", "CANAL",
                                   "STATUS_ENVIO", "MESSAGE_ID"]], hide_index=True,
                        width="stretch", height=330)
