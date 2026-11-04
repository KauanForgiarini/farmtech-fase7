"""Fase 5: infraestrutura e segurança na AWS (base do serviço de alertas da Fase 7)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.componentes import botao_servico, cabecalho
from farmtech_core.config import SRC
from fase7_alertas_aws import aws_config

CUSTOS_FASE5 = pd.DataFrame([
    {"Componente": "EC2 t3.micro (730 h)", "us-east-1 (US$/mês)": 7.59, "sa-east-1 (US$/mês)": 12.26},
    {"Componente": "EBS gp3 50 GB", "us-east-1 (US$/mês)": 4.00, "sa-east-1 (US$/mês)": 7.60},
    {"Componente": "Total", "us-east-1 (US$/mês)": 11.59, "sa-east-1 (US$/mês)": 19.86},
])
CUSTOS_FASE7 = pd.DataFrame([
    {"Serviço": "AWS Lambda", "Uso estimado/mês": "~3 mil invocações, 128 MB, <1 s",
     "Custo": "US$ 0,00 (nível gratuito: 1 milhão de requisições)"},
    {"Serviço": "Amazon SNS e-mail", "Uso estimado/mês": "~3 mil notificações",
     "Custo": "US$ 0,00 (1 mil e-mails grátis; depois US$ 2 por 100 mil)"},
    {"Serviço": "Amazon SNS SMS (Brasil)", "Uso estimado/mês": "~100 SMS críticos",
     "Custo": "≈ US$ 0,02 a 0,05 por SMS (varia por operadora)"},
    {"Serviço": "Amazon S3", "Uso estimado/mês": "< 50 MB de eventos JSON",
     "Custo": "< US$ 0,01"},
])
CONTROLES = [
    "Credenciais fora do código: o boto3 lê o ~/.aws/credentials do Learner Lab; `.env` e "
    "`data/aws_config.json` estão no .gitignore.",
    "Bucket S3 privado: Block Public Access ativado, criptografia SSE-S3 (AES-256) e política "
    "que nega acesso sem HTTPS (aws:SecureTransport).",
    "Lambda com a LabRole (o Learner Lab não permite criar roles). Em produção: role dedicada "
    "com a política de menor privilégio de `src/fase5_infra_aws/politica_minimo_privilegio.json`.",
    "SNS com assinaturas confirmadas pelo destinatário (double opt-in) e filtro por severidade "
    "para SMS; criptografia opcional com a chave KMS gerenciada aws/sns (`--sns-kms`).",
    "Logs de execução no Amazon CloudWatch Logs para auditoria de cada alerta enviado.",
    "Região: us-east-1 no Learner Lab (única liberada com us-west-2). Em produção, sa-east-1 "
    "(São Paulo), decisão da Fase 5 pela restrição de armazenar os dados no Brasil.",
]


def render() -> None:
    cabecalho("☁️ Fase 5 — Infraestrutura e segurança na AWS",
              "Base em nuvem que hospeda o serviço de mensageria da Fase 7")

    config = aws_config.carregar()
    esquerda, direita = st.columns([3, 2])
    with esquerda:
        st.subheader("Arquitetura na AWS")
        st.markdown("""
        `ESP32 / dashboard` → **Amazon S3** (`sensores/*.json`, `visao/*.json`) → gatilho →
        **AWS Lambda** `farmtech-alertas` (regras + ações corretivas) → **Amazon SNS**
        `farmtech-alertas` → e-mail e SMS dos funcionários · logs no **CloudWatch**.
        """)
        st.subheader("Controles de segurança")
        for controle in CONTROLES:
            st.markdown(f"- {controle}")
        with st.expander("Política IAM de menor privilégio (produção)"):
            st.code((SRC / "fase5_infra_aws" / "politica_minimo_privilegio.json")
                    .read_text(encoding="utf-8"), language="json")
    with direita:
        st.subheader("Conexão com a AWS")
        if st.button("Verificar credenciais AWS", width="stretch"):
            valido, detalhe = aws_config.credenciais_validas(config["regiao"])
            (st.success if valido else st.warning)(detalhe)
        st.json({k: v for k, v in config.items() if v}, expanded=False)
        with st.form("deploy"):
            st.markdown("**Implantar/atualizar o serviço de alertas**")
            email = st.text_input("E-mail do funcionário")
            telefone = st.text_input("Celular para SMS (opcional, +55...)")
            implantar = st.form_submit_button("Preparar implantação", width="stretch")
        if implantar and email:
            st.session_state["args_deploy"] = ["--email", email] + (
                ["--telefone", telefone] if telefone else [])
        if st.session_state.get("args_deploy"):
            botao_servico("aws-deploy", st.session_state["args_deploy"], "▶ Implantar na AWS",
                          "f5_deploy")

    st.subheader("Custos")
    a, b = st.columns(2)
    a.markdown("**Fase 5 — API de inferência em EC2 (cotação de 08/09/2026)**")
    a.dataframe(CUSTOS_FASE5, hide_index=True, width="stretch")
    b.markdown("**Fase 7 — serviço de alertas serverless (estimativa)**")
    b.dataframe(CUSTOS_FASE7, hide_index=True, width="stretch")
    st.caption("A arquitetura serverless (Lambda + SNS + S3) custa centavos por mês no volume da "
               "fazenda, contra cerca de US$ 12 a 20/mês de uma EC2 ligada 24 h.")
