"""
FarmTech Solutions - Fase 2: coleta das leituras do ESP32 e decisão de irrigação.

Duas fontes de dados, mesma saída (data/fase2_leituras_sensores.csv):

  1. Simulador (padrão): reproduz o comportamento físico do talhão hora a hora
     (evapotranspiração, chuva, irrigação, consumo de NPK, deriva do pH) e decide
     a bomba com a MESMA regra do firmware (regras_alerta.decidir_irrigacao).
  2. ESP32 real ou Wokwi for VS Code (--serial): lê as linhas "CSV,..." da Serial
     e envia ao ESP32 a previsão de chuva da Open-Meteo ('1' ou '0').

Uso:
    python simulador_esp32.py --leituras 72 --cenario realista
    python simulador_esp32.py --cenario seca --clima
    python simulador_esp32.py --serial COM3 --leituras 20
    python simulador_esp32.py --serial rfc2217://localhost:4000 --leituras 20
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmtech_core.config import ARQUIVOS, SEMENTE, configurar_saida
from fase2_iot_irrigacao.clima_open_meteo import obter_previsao
from fase7_alertas_aws.lambda_alertas.regras_alerta import LIMITES, MOTIVOS, decidir_irrigacao

ID_TALHAO_MONITORADO = 1   # "Talhão 1 - Soja Norte" (Fase 1)

COLUNAS = ["ID_LEITURA", "ID_TALHAO", "DATA_HORA", "N_PRESENTE", "P_PRESENTE", "K_PRESENTE",
           "N_KGHA", "P_KGHA", "K_KGHA", "PH_SOLO", "UMIDADE_SOLO_PCT", "TEMPERATURA_C",
           "CHUVA_PREVISTA_MM", "BOMBA_LIGADA", "MOTIVO_DECISAO", "ORIGEM"]

# Condições iniciais e taxas por cenário (para demonstrar cada tipo de alerta)
CENARIOS = {
    "normal":    dict(umidade=68, ph=6.4, deriva_ph=0.0, n=105, p=82, k=95, consumo=0.05,
                      temp_extra=0, prob_chuva=0.03, chuva_max=12),
    "realista":  dict(umidade=64, ph=6.1, deriva_ph=-0.009, n=92, p=66, k=86, consumo=0.13,
                      temp_extra=2, prob_chuva=0.02, chuva_max=14),
    "seca":      dict(umidade=50, ph=6.2, deriva_ph=0.0, n=74, p=55, k=72, consumo=0.05,
                      temp_extra=8, prob_chuva=0.0, chuva_max=0),
    "acidez":    dict(umidade=58, ph=5.6, deriva_ph=-0.013, n=95, p=75, k=90, consumo=0.05,
                      temp_extra=0, prob_chuva=0.02, chuva_max=10),
    "saturacao": dict(umidade=79, ph=6.5, deriva_ph=0.0, n=100, p=80, k=92, consumo=0.05,
                      temp_extra=-2, prob_chuva=0.25, chuva_max=32),
}


def simular(leituras: int, cenario: str, intervalo_min: int, semente: int,
            chuva_real_mm: float | None) -> list[dict]:
    cfg = CENARIOS[cenario]
    rng = random.Random(semente)
    umidade, ph = float(cfg["umidade"]), float(cfg["ph"])
    n, p, k = float(cfg["n"]), float(cfg["p"]), float(cfg["k"])
    horas_chuva, intensidade = 0, 0.0
    fim = datetime.now().replace(minute=0, second=0, microsecond=0)
    inicio = fim - timedelta(minutes=intervalo_min * (leituras - 1))
    passo_h = intervalo_min / 60
    registros = []

    for i in range(leituras):
        momento = inicio + timedelta(minutes=intervalo_min * i)
        hora = momento.hour + momento.minute / 60
        temperatura = (24 + cfg["temp_extra"] + 6 * math.sin(2 * math.pi * (hora - 9) / 24)
                       + rng.gauss(0, 0.8))

        # Previsão de chuva: eventos de algumas horas (a última pode vir da Open-Meteo)
        if horas_chuva == 0 and rng.random() < cfg["prob_chuva"]:
            horas_chuva, intensidade = rng.randint(3, 6), rng.uniform(6, cfg["chuva_max"])
        chuva = intensidade * rng.uniform(0.6, 1.2) if horas_chuva > 0 else 0.0
        horas_chuva = max(0, horas_chuva - 1)
        if i == leituras - 1 and chuva_real_mm is not None:
            chuva = chuva_real_mm

        p_presente = p >= LIMITES["p_min_kgha"]
        k_presente = k >= LIMITES["k_min_kgha"]
        ph_lido = ph + rng.gauss(0, 0.04)
        umidade_lida = min(95.0, max(15.0, umidade + rng.gauss(0, 0.6)))
        bomba, motivo = decidir_irrigacao(umidade_lida, ph_lido, chuva, p_presente, k_presente)

        registros.append({
            "ID_LEITURA": i + 1, "ID_TALHAO": ID_TALHAO_MONITORADO,
            "DATA_HORA": momento.strftime("%Y-%m-%d %H:%M:%S"),
            "N_PRESENTE": int(n >= LIMITES["n_min_kgha"]), "P_PRESENTE": int(p_presente),
            "K_PRESENTE": int(k_presente), "N_KGHA": round(n, 1), "P_KGHA": round(p, 1),
            "K_KGHA": round(k, 1), "PH_SOLO": round(ph_lido, 2),
            "UMIDADE_SOLO_PCT": round(umidade_lida, 1), "TEMPERATURA_C": round(temperatura, 1),
            "CHUVA_PREVISTA_MM": round(chuva, 1), "BOMBA_LIGADA": int(bomba),
            "MOTIVO_DECISAO": motivo, "ORIGEM": f"simulador:{cenario}",
        })

        # Dinâmica do solo até a próxima leitura
        evapotranspiracao = max(0.08, 0.15 + 0.025 * (temperatura - 20)) * passo_h
        umidade += -evapotranspiracao + (2.5 * passo_h if bomba else 0.0) + 0.3 * chuva * passo_h
        umidade = min(95.0, max(15.0, umidade))
        ph += cfg["deriva_ph"] * passo_h
        n -= cfg["consumo"] * 1.2 * passo_h
        p -= cfg["consumo"] * passo_h
        k -= cfg["consumo"] * passo_h
    return registros


def ler_serial(porta: str, leituras: int, chuva_prevista: bool) -> list[dict]:
    """Lê o ESP32 real (COMx) ou o Wokwi for VS Code (rfc2217://localhost:4000)."""
    import serial  # pyserial

    registros = []
    conexao = serial.serial_for_url(porta, baudrate=115200, timeout=5)
    print(f"Conectado em {porta}. Aguardando {leituras} leituras do ESP32...")
    try:
        while len(registros) < leituras:
            conexao.write(b"1" if chuva_prevista else b"0")
            linha = conexao.readline().decode("utf-8", errors="ignore").strip()
            if not linha.startswith("CSV,") or linha.startswith("CSV,N"):
                continue
            partes = linha.split(",")
            if len(partes) < 9:
                continue
            n, p, k = (int(v) for v in partes[1:4])
            registros.append({
                "ID_LEITURA": len(registros) + 1, "ID_TALHAO": ID_TALHAO_MONITORADO,
                "DATA_HORA": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "N_PRESENTE": n, "P_PRESENTE": p, "K_PRESENTE": k,
                # o botão informa só presente/ausente; o valor contínuo é o típico da faixa
                "N_KGHA": 95.0 if n else 65.0, "P_KGHA": 75.0 if p else 45.0,
                "K_KGHA": 95.0 if k else 65.0,
                "PH_SOLO": float(partes[4]), "UMIDADE_SOLO_PCT": float(partes[5]),
                "TEMPERATURA_C": float(partes[6]),
                "CHUVA_PREVISTA_MM": LIMITES["chuva_limiar_mm"] if partes[7] == "1" else 0.0,
                "BOMBA_LIGADA": int(partes[8]),
                "MOTIVO_DECISAO": partes[9] if len(partes) > 9 else "",
                "ORIGEM": "esp32",
            })
            print("  ", linha)
    finally:
        conexao.close()
    return registros


def salvar(registros: list[dict], anexar: bool) -> None:
    arquivo = ARQUIVOS["leituras"]
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    if anexar and arquivo.exists():
        with open(arquivo, encoding="utf-8") as f:
            ultimo = max((int(l["ID_LEITURA"]) for l in csv.DictReader(f)), default=0)
        for i, r in enumerate(registros, start=1):
            r["ID_LEITURA"] = ultimo + i
    with open(arquivo, "a" if anexar and arquivo.exists() else "w",
              encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        if f.tell() == 0:
            escritor.writeheader()
        escritor.writerows(registros)


def imprimir_resumo(registros: list[dict]) -> None:
    ligadas = sum(r["BOMBA_LIGADA"] for r in registros)
    print(f"{len(registros)} leituras | bomba ligada em {ligadas} "
          f"({100 * ligadas / len(registros):.0f}%)")
    contagem: dict[str, int] = {}
    for r in registros:
        contagem[r["MOTIVO_DECISAO"]] = contagem.get(r["MOTIVO_DECISAO"], 0) + 1
    for motivo, total in sorted(contagem.items(), key=lambda x: -x[1]):
        print(f"  {motivo:<17} {total:>4}  {MOTIVOS.get(motivo, '')}")
    u = registros[-1]
    print("\nÚltima leitura (formato do Monitor Serial do ESP32):")
    print(f"  NPK -> N:{'SIM' if u['N_PRESENTE'] else 'NAO'} | "
          f"P:{'SIM' if u['P_PRESENTE'] else 'NAO'} | K:{'SIM' if u['K_PRESENTE'] else 'NAO'}")
    print(f"  pH: {u['PH_SOLO']:.2f} | Umidade solo: {u['UMIDADE_SOLO_PCT']:.1f}% | "
          f"Temp: {u['TEMPERATURA_C']:.1f} C | Chuva prevista: {u['CHUVA_PREVISTA_MM']:.1f} mm")
    print(f"  Bomba: {'LIGADA' if u['BOMBA_LIGADA'] else 'DESLIGADA'} ({u['MOTIVO_DECISAO']})")


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Leituras do ESP32 (Fase 2)")
    parser.add_argument("--leituras", type=int, default=72)
    parser.add_argument("--cenario", choices=sorted(CENARIOS), default="realista")
    parser.add_argument("--intervalo-min", type=int, default=60)
    parser.add_argument("--semente", type=int, default=SEMENTE)
    parser.add_argument("--clima", action="store_true",
                        help="usa a chuva prevista real (Open-Meteo) na última leitura")
    parser.add_argument("--serial", metavar="PORTA", help="COM3, /dev/ttyUSB0 ou rfc2217://...")
    parser.add_argument("--anexar", action="store_true", help="acrescenta ao CSV existente")
    args = parser.parse_args()

    chuva_real = None
    if args.clima or args.serial:
        previsao = obter_previsao()
        if previsao:
            chuva_real = previsao["chuva_proxima_hora_mm"]
            print(f"Open-Meteo: {chuva_real:.1f} mm previstos na próxima hora "
                  f"({previsao['cidade']}).")
        else:
            print("Open-Meteo indisponível: considerando sem chuva prevista.")

    if args.serial:
        chuva_prevista = (chuva_real or 0.0) >= LIMITES["chuva_limiar_mm"]
        registros = ler_serial(args.serial, args.leituras, chuva_prevista)
    else:
        registros = simular(args.leituras, args.cenario, args.intervalo_min, args.semente,
                            chuva_real)
        print(f"Simulador ESP32 - cenário '{args.cenario}', semente {args.semente}")
    salvar(registros, args.anexar)
    imprimir_resumo(registros)
    print(f"\nArquivo gerado: {ARQUIVOS['leituras'].relative_to(ARQUIVOS['leituras'].parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
