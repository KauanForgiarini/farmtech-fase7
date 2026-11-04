"""
FarmTech Solutions - Fase 4: pipeline de Machine Learning (regressão).

1. Treina 4 regressores (Linear, Ridge, Random Forest, Gradient Boosting) para
   cada alvo agronômico, com divisão 80/20 e validação cruzada 5-fold;
2. salva o melhor modelo de cada alvo (joblib) e as métricas (metadata.json);
3. aplica os modelos às leituras atuais do ESP32 (Fase 2) e grava
   data/fase4_previsoes.csv, carregado no banco (Fase 3) e usado pelos
   alertas da Fase 7 (volume de irrigação sugerido).

Uso:
    python src/fase4_modelos_preditivos/treinar_modelos.py            # treina e prevê
    python src/fase4_modelos_preditivos/treinar_modelos.py --somente-prever
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from farmtech_core.config import ARQUIVOS, PASTA_MODELOS_ML, SEMENTE, configurar_saida
from fase4_modelos_preditivos.gerar_historico import gerar

FEATURES = ["UMIDADE_SOLO_PCT", "PH_SOLO", "TEMPERATURA_C", "CHUVA_PREVISTA_MM",
            "N_KGHA", "P_KGHA", "K_KGHA"]
ALVOS = {
    "volume_irrigacao": "VOLUME_IRRIGACAO_L",
    "necessidade_fert": "NECESSIDADE_FERT_KGHA",
    "rendimento_esperado": "RENDIMENTO_ESPERADO_SCHA",
}
META = PASTA_MODELOS_ML / "metadata.json"


def candidatos() -> dict:
    return {
        "Regressão Linear": LinearRegression(),
        "Ridge": Ridge(alpha=1.0),
        "Random Forest": RandomForestRegressor(n_estimators=200, random_state=SEMENTE),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=150, random_state=SEMENTE),
    }


def treinar(df: pd.DataFrame) -> dict:
    PASTA_MODELOS_ML.mkdir(parents=True, exist_ok=True)
    X = df[FEATURES]
    resultados = {}
    validacao = KFold(n_splits=5, shuffle=True, random_state=SEMENTE)
    for nome_alvo, coluna in ALVOS.items():
        y = df[coluna]
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=SEMENTE)
        metricas, melhor = {}, (None, -np.inf, None)
        for nome_modelo, modelo in candidatos().items():
            pipe = Pipeline([("scaler", StandardScaler()), ("model", modelo)])
            pipe.fit(X_tr, y_tr)
            pred = pipe.predict(X_te)
            cv = cross_val_score(pipe, X, y, cv=validacao, scoring="r2")
            metricas[nome_modelo] = {
                "MAE": round(mean_absolute_error(y_te, pred), 4),
                "RMSE": round(float(np.sqrt(mean_squared_error(y_te, pred))), 4),
                "R2": round(r2_score(y_te, pred), 4),
                "CV_R2_media": round(cv.mean(), 4), "CV_R2_desvio": round(cv.std(), 4),
            }
            # o critério de escolha é o R² médio da validação cruzada (mais estável)
            if cv.mean() > melhor[1]:
                melhor = (nome_modelo, cv.mean(), pipe)
        nome_modelo, cv_r2, pipe = melhor
        pipe.fit(X, y)                                  # modelo final com todos os dados
        joblib.dump(pipe, PASTA_MODELOS_ML / f"modelo_{nome_alvo}.joblib")
        importancia = None
        if hasattr(pipe.named_steps["model"], "feature_importances_"):
            importancia = dict(zip(FEATURES, np.round(
                pipe.named_steps["model"].feature_importances_, 4).tolist()))
        resultados[nome_alvo] = {"coluna": coluna, "melhor_modelo": nome_modelo,
                                 "melhor_cv_r2": round(cv_r2, 4), "modelos": metricas,
                                 "importancia_features": importancia}
        print(f"\n[{coluna}] melhor: {nome_modelo} (CV-R² = {cv_r2:.3f})")
        for nome, m in metricas.items():
            print(f"   {nome:<18} MAE={m['MAE']:<8} RMSE={m['RMSE']:<8} R²={m['R2']:<8} "
                  f"CV-R²={m['CV_R2_media']}±{m['CV_R2_desvio']}")
    META.write_text(json.dumps({"features": FEATURES, "alvos": ALVOS,
                                "amostras_treino": len(df), "resultados": resultados},
                               indent=2, ensure_ascii=False), encoding="utf-8")
    return resultados


def carregar_modelos() -> dict:
    return {nome: joblib.load(PASTA_MODELOS_ML / f"modelo_{nome}.joblib")
            for nome in ALVOS if (PASTA_MODELOS_ML / f"modelo_{nome}.joblib").exists()}


def prever(modelos: dict, entrada: pd.DataFrame) -> pd.DataFrame:
    saida = pd.DataFrame(index=entrada.index)
    for nome, modelo in modelos.items():
        saida[ALVOS[nome]] = np.clip(modelo.predict(entrada[FEATURES]), 0, None).round(2)
    return saida


def prever_leituras_atuais() -> int:
    if not ARQUIVOS["leituras"].exists():
        print("Sem leituras da Fase 2 para prever (execute: python farmtech.py fase2).")
        return 0
    modelos = carregar_modelos()
    leituras = pd.read_csv(ARQUIVOS["leituras"])
    previsoes = prever(modelos, leituras)
    previsoes.insert(0, "ID_LEITURA", leituras["ID_LEITURA"])
    meta = json.loads(META.read_text(encoding="utf-8"))
    previsoes["MODELO"] = meta["resultados"]["volume_irrigacao"]["melhor_modelo"]
    previsoes.to_csv(ARQUIVOS["previsoes"], index=False)
    ultima = previsoes.iloc[-1]
    print(f"\nPrevisões para {len(previsoes)} leituras do ESP32 salvas em "
          f"{ARQUIVOS['previsoes'].name}. Última leitura:")
    print(f"   Volume de irrigação sugerido: {ultima['VOLUME_IRRIGACAO_L']:.2f} L/m²")
    print(f"   Necessidade de fertilização : {ultima['NECESSIDADE_FERT_KGHA']:.1f} kg/ha")
    print(f"   Rendimento esperado          : {ultima['RENDIMENTO_ESPERADO_SCHA']:.1f} sc/ha")
    return len(previsoes)


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Modelos preditivos FarmTech (Fase 4)")
    parser.add_argument("--somente-prever", action="store_true")
    args = parser.parse_args()

    if not args.somente_prever:
        if not ARQUIVOS["historico_ml"].exists():
            gerar().to_csv(ARQUIVOS["historico_ml"], index=False)
        historico = pd.read_csv(ARQUIVOS["historico_ml"])
        print(f"Treinando com {len(historico)} leituras históricas "
              f"({ARQUIVOS['historico_ml'].name})")
        treinar(historico)
    prever_leituras_atuais()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
