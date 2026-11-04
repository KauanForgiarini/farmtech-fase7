"""
FarmTech Solutions - Fase 2: previsão de chuva pela API Open-Meteo.

API gratuita e sem chave (https://open-meteo.com). A precipitação prevista
para a próxima hora é enviada ao ESP32 ('1' = chuva prevista, '0' = sem chuva)
e entra na decisão de irrigação.

Uso:
    python src/fase2_iot_irrigacao/clima_open_meteo.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from farmtech_core.config import ARQUIVOS, configurar_saida

CIDADE = "Santa Maria - RS"
LATITUDE, LONGITUDE = -29.6842, -53.8069
URL = "https://api.open-meteo.com/v1/forecast"


def obter_previsao(horas: int = 24, timeout: int = 10) -> dict | None:
    """Retorna a previsão horária de chuva e temperatura ou None se estiver offline."""
    parametros = {
        "latitude": LATITUDE, "longitude": LONGITUDE,
        "hourly": "precipitation,temperature_2m,relative_humidity_2m",
        "forecast_days": 2, "timezone": "America/Sao_Paulo",
    }
    try:
        resposta = requests.get(URL, params=parametros, timeout=timeout)
        resposta.raise_for_status()
        horario = resposta.json()["hourly"]
    except (requests.RequestException, KeyError, ValueError):
        return None

    agora = datetime.now().strftime("%Y-%m-%dT%H:00")
    inicio = horario["time"].index(agora) if agora in horario["time"] else 0
    fim = inicio + horas
    previsao = {
        "cidade": CIDADE,
        "consultado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "horas": horario["time"][inicio:fim],
        "chuva_mm": horario["precipitation"][inicio:fim],
        "temperatura_c": horario["temperature_2m"][inicio:fim],
        "umidade_ar_pct": horario["relative_humidity_2m"][inicio:fim],
    }
    previsao["chuva_proxima_hora_mm"] = float(previsao["chuva_mm"][0] or 0.0)
    previsao["chuva_24h_mm"] = round(sum(v or 0.0 for v in previsao["chuva_mm"]), 1)
    ARQUIVOS["clima"].parent.mkdir(parents=True, exist_ok=True)
    ARQUIVOS["clima"].write_text(json.dumps(previsao, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    return previsao


def main() -> int:
    configurar_saida()
    previsao = obter_previsao()
    if previsao is None:
        print("Sem conexão com a Open-Meteo: o sistema assume 'sem chuva prevista'.")
        return 1
    print(f"Previsão para {previsao['cidade']} (consulta {previsao['consultado_em']}):")
    print(f"  Chuva na próxima hora: {previsao['chuva_proxima_hora_mm']:.1f} mm")
    print(f"  Chuva nas próximas 24 h: {previsao['chuva_24h_mm']:.1f} mm")
    print(f"  Temperatura agora: {previsao['temperatura_c'][0]:.1f} °C")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
