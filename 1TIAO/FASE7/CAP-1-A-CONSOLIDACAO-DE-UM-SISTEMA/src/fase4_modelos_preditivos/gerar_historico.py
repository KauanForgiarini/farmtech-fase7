"""
FarmTech Solutions - Fase 4: histórico de treinamento dos modelos de regressão.

Gera 200 leituras históricas (semente 574005) com as variáveis-alvo agronômicas
da Fase 4: volume de irrigação (L/m²), necessidade de fertilização (kg/ha) e
rendimento esperado de soja (sc/ha). A decisão da bomba usa a mesma regra do
firmware ESP32, mantendo a consistência com as Fases 2 e 3.

Uso:
    python src/fase4_modelos_preditivos/gerar_historico.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from farmtech_core.config import ARQUIVOS, SEMENTE, configurar_saida
from fase7_alertas_aws.lambda_alertas.regras_alerta import LIMITES, decidir_irrigacao


def gerar(n_amostras: int = 200, semente: int = SEMENTE) -> pd.DataFrame:
    rng = np.random.default_rng(semente)
    inicio = datetime(2025, 1, 1, 6, 0, 0)
    registros = []
    for i in range(n_amostras):
        umidade = round(rng.uniform(30, 95), 1)
        ph = round(rng.uniform(4.5, 8.0), 2)
        temperatura = round(rng.uniform(18, 35), 1)
        chuva = round(max(0.0, rng.exponential(3)), 1)
        n_kgha = round(rng.uniform(40, 130), 1)
        p_kgha = round(rng.uniform(30, 100), 1)
        k_kgha = round(rng.uniform(40, 110), 1)

        # Alvo 1: volume de irrigação (L/m²) - déficit até 70% ajustado por pH, chuva e calor
        fator_ph = 1.0 if 5.5 <= ph <= 7.0 else 0.5
        volume = (max(0, 70 - umidade) * 0.15 * fator_ph * max(0, 1 - chuva / 10)
                  * (1 + (temperatura - 25) * 0.02) + rng.normal(0, 0.3))

        # Alvo 2: necessidade de fertilização (kg/ha) - déficit de NPK + correção de pH
        fert = ((max(0, 100 - n_kgha) * 0.4 + max(0, 75 - p_kgha) * 0.35
                 + max(0, 90 - k_kgha) * 0.25) * 0.5 + abs(6.2 - ph) * 5 + rng.normal(0, 1.5))

        # Alvo 3: rendimento esperado de soja (sc/ha) - média regional de 55 sc/ha
        rendimento = (55 * (1 - abs(umidade - 70) * 0.008) * (1 - abs(ph - 6.2) * 0.1)
                      * ((min(1, n_kgha / 100) + min(1, p_kgha / 75) + min(1, k_kgha / 90)) / 3)
                      * max(0.5, 1 - abs(temperatura - 24) * 0.015) + rng.normal(0, 2))

        p_presente = p_kgha >= LIMITES["p_min_kgha"]
        k_presente = k_kgha >= LIMITES["k_min_kgha"]
        bomba, motivo = decidir_irrigacao(umidade, ph, chuva, p_presente, k_presente)
        registros.append({
            "ID": i + 1,
            "DATA_HORA": (inicio + timedelta(hours=3 * i)).strftime("%Y-%m-%d %H:%M:%S"),
            "N_PRESENTE": int(n_kgha >= LIMITES["n_min_kgha"]), "P_PRESENTE": int(p_presente),
            "K_PRESENTE": int(k_presente), "N_KGHA": n_kgha, "P_KGHA": p_kgha, "K_KGHA": k_kgha,
            "PH_SOLO": ph, "UMIDADE_SOLO_PCT": umidade, "TEMPERATURA_C": temperatura,
            "CHUVA_PREVISTA_MM": chuva, "BOMBA_LIGADA": int(bomba), "MOTIVO_DECISAO": motivo,
            "VOLUME_IRRIGACAO_L": round(max(0, volume), 2),
            "NECESSIDADE_FERT_KGHA": round(max(0, fert), 2),
            "RENDIMENTO_ESPERADO_SCHA": round(min(80, max(10, rendimento)), 2),
        })
    return pd.DataFrame(registros)


def main() -> int:
    configurar_saida()
    df = gerar()
    ARQUIVOS["historico_ml"].parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ARQUIVOS["historico_ml"], index=False)
    print(f"Histórico gerado: {len(df)} registros em {ARQUIVOS['historico_ml'].name}")
    print(df[["VOLUME_IRRIGACAO_L", "NECESSIDADE_FERT_KGHA", "RENDIMENTO_ESPERADO_SCHA"]]
          .describe().round(2).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
