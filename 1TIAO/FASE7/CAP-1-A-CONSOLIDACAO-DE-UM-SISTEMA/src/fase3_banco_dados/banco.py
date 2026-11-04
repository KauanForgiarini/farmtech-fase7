"""
FarmTech Solutions - Camada de acesso ao banco de dados (Fase 3).

Dois backends com o mesmo modelo relacional e as mesmas consultas:
  * oracle  - Oracle da FIAP (oracle.fiap.com.br), via driver oracledb (modo thin);
  * sqlite  - arquivo data/farmtech.db, padrão para rodar sem a rede da FIAP.

O backend é escolhido pela variável FARMTECH_DB (arquivo .env na raiz).
As consultas usam parâmetros nomeados (:nome), aceitos pelos dois drivers.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
from pathlib import Path

from farmtech_core.config import ARQUIVOS

PASTA_SQL = Path(__file__).resolve().parent / "sql"
TABELAS = ["CULTURA", "TALHAO", "APLICACAO_INSUMO", "LEITURA_SENSOR",
           "PREVISAO_ML", "DETECCAO_VISAO", "ALERTA"]


def _nativo(valor):
    """Converte tipos numpy/pandas e NaN para tipos aceitos pelos drivers."""
    if hasattr(valor, "item"):
        valor = valor.item()
    if isinstance(valor, float) and math.isnan(valor):
        return None
    return valor


def ler_blocos_sql(arquivo: Path) -> list[str]:
    """Divide um script SQL em comandos, ignorando comentários de linha."""
    linhas = [l for l in arquivo.read_text(encoding="utf-8").splitlines()
              if not l.strip().startswith("--")]
    return [c.strip() for c in "\n".join(linhas).split(";") if c.strip()]


def ler_consultas_nomeadas(arquivo: Path = PASTA_SQL / "consultas.sql") -> dict[str, str]:
    """Lê consultas no formato '-- nome: xxx' seguido do SELECT."""
    consultas, atual, corpo = {}, None, []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        marcador = re.match(r"--\s*nome:\s*(\w+)", linha.strip())
        if marcador:
            if atual:
                consultas[atual] = "\n".join(corpo).strip().rstrip(";")
            atual, corpo = marcador.group(1), []
        elif atual and not linha.strip().startswith("--"):
            corpo.append(linha)
    if atual:
        consultas[atual] = "\n".join(corpo).strip().rstrip(";")
    return consultas


class Banco:
    def __init__(self, backend: str | None = None):
        self.backend = (backend or os.getenv("FARMTECH_DB", "sqlite")).strip().lower()
        self.conexao = self._conectar()

    # ----------------------------------------------------------------- conexão
    def _conectar(self):
        if self.backend == "oracle":
            import oracledb  # import tardio: só é necessário no modo Oracle

            dsn = os.getenv("ORACLE_DSN") or oracledb.makedsn(
                os.getenv("ORACLE_HOST", "oracle.fiap.com.br"),
                int(os.getenv("ORACLE_PORT", "1521")),
                sid=os.getenv("ORACLE_SID", "ORCL"),
            )
            return oracledb.connect(user=os.environ["ORACLE_USER"],
                                    password=os.environ["ORACLE_PASSWORD"], dsn=dsn)
        if self.backend != "sqlite":
            raise ValueError(f"Backend desconhecido: {self.backend} (use sqlite ou oracle)")
        ARQUIVOS["banco_sqlite"].parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(ARQUIVOS["banco_sqlite"])
        conexao.execute("PRAGMA foreign_keys = ON")
        return conexao

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fechar()

    def fechar(self):
        if self.conexao is not None:
            self.conexao.close()
            self.conexao = None

    @property
    def descricao(self) -> str:
        if self.backend == "oracle":
            return f"Oracle ({os.getenv('ORACLE_HOST', 'oracle.fiap.com.br')})"
        return f"SQLite ({ARQUIVOS['banco_sqlite'].name})"

    # ------------------------------------------------------------------ esquema
    def recriar_esquema(self) -> None:
        cursor = self.conexao.cursor()
        for tabela in reversed(TABELAS):
            if self.backend == "oracle":
                try:
                    cursor.execute(f"DROP TABLE {tabela} CASCADE CONSTRAINTS PURGE")
                except Exception:  # tabela ainda não existe
                    pass
            else:
                cursor.execute(f"DROP TABLE IF EXISTS {tabela}")
        script = (PASTA_SQL / "oracle" / "01_ddl_farmtech.sql" if self.backend == "oracle"
                  else PASTA_SQL / "sqlite_schema.sql")
        for comando in ler_blocos_sql(script):
            cursor.execute(comando)
        self.conexao.commit()

    def tabelas_existem(self) -> bool:
        try:
            self.consultar("SELECT COUNT(*) AS TOTAL FROM LEITURA_SENSOR")
            return True
        except Exception:
            return False

    # ----------------------------------------------------------------- operações
    def inserir(self, tabela: str, registros: list[dict]) -> int:
        if not registros:
            return 0
        colunas = list(registros[0].keys())
        sql = (f"INSERT INTO {tabela} ({', '.join(colunas)}) "
               f"VALUES ({', '.join(':' + c for c in colunas)})")
        linhas = [{c: _nativo(r.get(c)) for c in colunas} for r in registros]
        self.conexao.cursor().executemany(sql, linhas)
        self.conexao.commit()
        return len(linhas)

    def consultar(self, sql: str, parametros: dict | None = None) -> list[dict]:
        cursor = self.conexao.cursor()
        cursor.execute(sql, parametros or {})
        colunas = [d[0].upper() for d in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]

    def dataframe(self, sql: str, parametros: dict | None = None):
        import pandas as pd

        return pd.DataFrame(self.consultar(sql, parametros))

    def contagens(self) -> dict[str, int]:
        return {t: self.consultar(f"SELECT COUNT(*) AS TOTAL FROM {t}")[0]["TOTAL"]
                for t in TABELAS}
