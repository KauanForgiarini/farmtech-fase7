"""
Registro único dos serviços do sistema integrado.

O mesmo catálogo é usado pelo lançador de terminal (farmtech.py) e pelos botões
da dashboard. Cada serviço continua sendo um programa independente, executado
como subprocesso, o que mantém as fases desacopladas.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

from farmtech_core.config import RAIZ, SRC


@dataclass(frozen=True)
class Servico:
    chave: str
    fase: str
    nome: str
    script: str                       # caminho relativo à raiz do projeto
    descricao: str
    args_padrao: tuple = field(default_factory=tuple)
    atualiza_banco: bool = False      # roda o ETL da Fase 3 depois


SERVICOS: dict[str, Servico] = {s.chave: s for s in [
    Servico("fase1", "Fase 1", "Plantio e insumos (Python)",
            "src/fase1_plantio_insumos/farmtech_fase1.py",
            "Calcula área de plantio e insumos de soja e milho e exporta a base de dados.",
            ("--exemplo",), atualiza_banco=True),
    Servico("fase1-estatistica", "Fase 1", "Análise estatística (R ou Python)",
            "src/fase1_plantio_insumos/analise_estatistica.py",
            "Estatística descritiva dos talhões e dos sensores; usa o Rscript se instalado."),
    Servico("fase2", "Fase 2", "Sensores ESP32 e irrigação",
            "src/fase2_iot_irrigacao/simulador_esp32.py",
            "Gera leituras do ESP32 (simulador fiel ao firmware ou Serial/Wokwi) e decide a bomba.",
            ("--leituras", "72"), atualiza_banco=True),
    Servico("fase3", "Fase 3", "Banco de dados (ETL + consultas)",
            "src/fase3_banco_dados/carga_banco.py",
            "Recria o esquema relacional e carrega todos os dados no SQLite ou no Oracle."),
    Servico("fase4", "Fase 4", "Modelos preditivos (treino + previsão)",
            "src/fase4_modelos_preditivos/treinar_modelos.py",
            "Treina os regressores e prevê irrigação, adubação e rendimento das leituras.",
            atualiza_banco=True),
    Servico("fase6", "Fase 6", "Visão computacional (YOLO)",
            "src/fase6_visao_computacional/detectar.py",
            "Detecta pessoas e veículos nas imagens das câmeras com o YOLO treinado na Fase 6.",
            atualiza_banco=True),
    Servico("alertas", "Fase 7", "Alertas na AWS (Lambda + SNS)",
            "src/fase7_alertas_aws/publicar_alerta.py",
            "Avalia sensores e visão, gera ações corretivas e envia e-mail/SMS pela AWS.",
            ("--modo", "auto"), atualiza_banco=True),
    Servico("aws-deploy", "Fase 7", "Implantar infraestrutura AWS",
            "src/fase7_alertas_aws/deploy_aws.py",
            "Cria tópico SNS, bucket S3 e função Lambda no AWS Academy Learner Lab."),
]}

# Serviços que alimentam o banco já disparam o ETL da Fase 3 ao terminar;
# a última execução da Fase 3 imprime as consultas analíticas finais.
ORDEM_PIPELINE = ["fase1", "fase2", "fase1-estatistica", "fase4", "fase6", "alertas", "fase3"]


def ambiente_filho() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def montar_comando(chave: str, args: list[str] | None = None) -> list[str]:
    servico = SERVICOS[chave]
    argumentos = list(servico.args_padrao if args is None else args)
    return [sys.executable, str(RAIZ / servico.script), *argumentos]


def comando_terminal(chave: str, args: list[str] | None = None) -> str:
    """Comando equivalente exibido na dashboard (botão = comando de terminal)."""
    servico = SERVICOS[chave]
    argumentos = list(servico.args_padrao if args is None else args)
    return " ".join(["python farmtech.py", chave, *argumentos]).strip()


def executar(chave: str, args: list[str] | None = None, timeout: int = 1800,
             capturar: bool = True) -> dict:
    """Executa um serviço e devolve código de saída, saída padrão e duração."""
    inicio = time.perf_counter()
    processo = subprocess.run(
        montar_comando(chave, args), cwd=RAIZ, env=ambiente_filho(),
        capture_output=capturar, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    resultado = {
        "servico": chave,
        "codigo": processo.returncode,
        "saida": (processo.stdout or "") + (processo.stderr or "") if capturar else "",
        "duracao_s": round(time.perf_counter() - inicio, 2),
    }
    if processo.returncode == 0 and SERVICOS[chave].atualiza_banco and chave != "fase3":
        etl = subprocess.run(montar_comando("fase3", ["--silencioso"]), cwd=RAIZ,
                             env=ambiente_filho(), capture_output=capturar, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout)
        if capturar:
            resultado["saida"] += "\n[ETL Fase 3] " + (etl.stdout or "").strip()
            if etl.returncode != 0:
                resultado["saida"] += "\n" + (etl.stderr or "")
    return resultado
