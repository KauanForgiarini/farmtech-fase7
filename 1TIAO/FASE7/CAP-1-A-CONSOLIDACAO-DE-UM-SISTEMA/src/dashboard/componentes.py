"""Componentes compartilhados pelas páginas da dashboard FarmTech."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from farmtech_core.config import ARQUIVOS
from farmtech_core.servicos import SERVICOS, comando_terminal, executar
from fase3_banco_dados.banco import Banco, ler_consultas_nomeadas

CORES = {"CRITICO": "#b42318", "ALTO": "#d97706", "MEDIO": "#2563eb", "INFO": "#64748b"}
VERDE = "#2d6a4f"


def cabecalho(titulo: str, subtitulo: str) -> None:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1b4332,#2d6a4f 55%,#40916c);
                padding:1.1rem 1.6rem;border-radius:12px;margin-bottom:1rem;color:white">
      <div style="font-size:1.6rem;font-weight:700">{titulo}</div>
      <div style="opacity:.85">{subtitulo}</div>
    </div>""", unsafe_allow_html=True)


def rodar_servico(chave: str, args: list[str] | None, chave_saida: str) -> None:
    """Executa o serviço, guarda a saída na sessão e recarrega a página com os novos dados."""
    with st.spinner(f"Executando {SERVICOS[chave].nome}..."):
        resultado = executar(chave, args)
    resultado["comando"] = comando_terminal(chave, args)
    st.session_state[f"saida_{chave_saida}"] = resultado
    st.cache_data.clear()
    st.rerun()


def mostrar_saida(chave_saida: str) -> dict | None:
    resultado = st.session_state.get(f"saida_{chave_saida}")
    if resultado:
        ok = resultado["codigo"] == 0
        nome = SERVICOS[resultado["servico"]].nome
        (st.success if ok else st.error)(
            f"{nome}: {'concluído' if ok else 'erro'} em {resultado['duracao_s']} s")
        with st.expander("Saída do programa", expanded=not ok):
            st.code(f"$ {resultado['comando']}\n\n" + (resultado["saida"][-12000:]
                                                      or "(sem saída)"), language="text")
    return resultado


def botao_servico(chave: str, args: list[str] | None = None, rotulo: str | None = None,
                  chave_widget: str | None = None, tipo: str = "primary") -> dict | None:
    """Botão que dispara um serviço e mostra o comando de terminal equivalente."""
    chave_widget = chave_widget or f"btn_{chave}"
    st.caption(f"Terminal: `{comando_terminal(chave, args)}`")
    if st.button(rotulo or f"▶ Executar {SERVICOS[chave].nome}", key=chave_widget,
                 type=tipo, width="stretch"):
        rodar_servico(chave, args, chave_widget)
    return mostrar_saida(chave_widget)


@st.cache_data(show_spinner=False)
def consultar(sql: str) -> pd.DataFrame:
    try:
        with Banco() as banco:
            return banco.dataframe(sql)
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def consulta_nomeada(nome: str) -> pd.DataFrame:
    return consultar(ler_consultas_nomeadas()[nome])


@st.cache_data(show_spinner=False)
def ler_csv(chave: str) -> pd.DataFrame:
    arquivo = ARQUIVOS[chave]
    return pd.read_csv(arquivo) if arquivo.exists() else pd.DataFrame()


def ler_json(chave: str) -> dict:
    arquivo = ARQUIVOS[chave]
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}


def banco_pronto() -> bool:
    try:
        with Banco() as banco:
            return banco.tabelas_existem()
    except Exception:
        return False


def selo_severidade(severidade: str) -> str:
    cor = CORES.get(severidade, "#64748b")
    return (f"<span style='background:{cor};color:white;padding:2px 8px;border-radius:6px;"
            f"font-size:.8rem;font-weight:600'>{severidade}</span>")


def cartao_alerta(alerta: dict) -> None:
    st.markdown(f"""
    <div style="border-left:5px solid {CORES.get(alerta['severidade'], '#64748b')};
                background:rgba(127,127,127,.08);border-radius:8px;padding:.7rem 1rem;
                margin-bottom:.6rem">
      {selo_severidade(alerta['severidade'])} <b>{alerta['titulo']}</b>
      <span style="opacity:.7"> — {alerta['local']} · {alerta['origem']}
      {f"· repetido {alerta['ocorrencias']}x" if alerta.get('ocorrencias', 1) > 1 else ''}</span>
      <div style="font-size:.85rem;opacity:.8;margin-top:.3rem">{alerta['evidencia']}</div>
      <div style="margin-top:.35rem"><b>Ação corretiva:</b> {alerta['acao']}</div>
      <div style="font-size:.85rem;opacity:.8">Responsável: {alerta['responsavel']}</div>
    </div>""", unsafe_allow_html=True)
