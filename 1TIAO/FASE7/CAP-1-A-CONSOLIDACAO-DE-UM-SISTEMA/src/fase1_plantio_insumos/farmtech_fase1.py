"""
FarmTech Solutions - Fase 1: área de plantio e manejo de insumos.

Aplicação de terminal que:
  * suporta duas culturas: SOJA (talhão retangular) e MILHO (pivô central circular);
  * calcula a área de plantio pela figura geométrica, o número de ruas e os
    metros lineares de plantio;
  * calcula o manejo de insumos (dose por hectare ou por metro linear de rua);
  * mantém os dados em vetores (listas) com menu de entrada, saída, atualização,
    deleção e saída do programa;
  * exporta a base de dados (CSV) usada pela análise em R e pelo banco da Fase 3.

Uso:
    python farmtech_fase1.py                       # menu interativo
    python farmtech_fase1.py --exemplo             # carrega os talhões de exemplo
    python farmtech_fase1.py --listar
    python farmtech_fase1.py --adicionar soja "Talhão 5" 300 200
    python farmtech_fase1.py --adicionar milho "Pivô 3" 150
    python farmtech_fase1.py --atualizar 2 450 260
    python farmtech_fase1.py --remover 4
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmtech_core.config import ARQUIVOS, configurar_saida
from fase7_alertas_aws.lambda_alertas.regras_alerta import CULTURAS

# Forma geométrica de cada cultura
FORMAS = {"soja": "RETANGULO", "milho": "CIRCULO"}

# Catálogo de insumos: (nome, tipo de dose, dose, unidade da dose, unidade do total)
INSUMOS = {
    "soja": [
        ("Fosfato monoamônico (MAP)", "POR_HA", 200.0, "kg/ha", "kg"),
        ("Cloreto de potássio (KCl)", "POR_HA", 100.0, "kg/ha", "kg"),
        ("Herbicida glifosato", "POR_HA", 3.0, "L/ha", "L"),
        ("Fungicida para ferrugem asiática", "POR_METRO", 0.5, "mL/m", "L"),
    ],
    "milho": [
        ("Formulado NPK 08-28-16", "POR_HA", 350.0, "kg/ha", "kg"),
        ("Ureia (nitrogênio em cobertura)", "POR_HA", 250.0, "kg/ha", "kg"),
        ("Inseticida para lagarta-do-cartucho", "POR_METRO", 0.3, "mL/m", "L"),
    ],
}

EXEMPLOS = [
    ("soja", "Talhão 1 - Soja Norte", 500.0, 300.0),
    ("soja", "Talhão 2 - Soja Sul", 400.0, 250.0),
    ("milho", "Pivô 1 - Milho", 250.0, None),
    ("milho", "Pivô 2 - Milho", 180.0, None),
]

COLUNAS_TALHAO = ["ID_TALHAO", "NOME", "CULTURA", "ID_CULTURA", "FORMA", "DIMENSAO_1_M",
                  "DIMENSAO_2_M", "AREA_M2", "AREA_HA", "NUM_RUAS", "METROS_LINEARES",
                  "DATA_CADASTRO"]
COLUNAS_INSUMO = ["ID_APLICACAO", "ID_TALHAO", "INSUMO", "TIPO_DOSE", "DOSE", "UNIDADE",
                  "QUANTIDADE_TOTAL", "UNIDADE_TOTAL"]

# Vetor principal com os talhões cadastrados
talhoes: list[dict] = []


# ----------------------------------------------------------------- cálculos
def calcular_area(cultura: str, dimensao_1: float, dimensao_2: float | None) -> float:
    """Soja: retângulo (comprimento x largura). Milho: círculo (pi x raio²)."""
    if dimensao_1 <= 0 or (FORMAS[cultura] == "RETANGULO" and (dimensao_2 or 0) <= 0):
        raise ValueError("As dimensões devem ser maiores que zero.")
    if FORMAS[cultura] == "RETANGULO":
        return dimensao_1 * dimensao_2
    return math.pi * dimensao_1 ** 2


def calcular_ruas(cultura: str, dimensao_1: float, dimensao_2: float | None,
                  area_m2: float) -> tuple[int, float]:
    """Número de ruas (linhas de plantio) e metros lineares totais."""
    espacamento = CULTURAS[cultura]["espacamento_m"]
    if FORMAS[cultura] == "RETANGULO":
        ruas = int(dimensao_2 // espacamento)        # ruas ao longo da largura
        return ruas, ruas * dimensao_1
    ruas = int((2 * dimensao_1) // espacamento)      # ruas atravessando o diâmetro
    return ruas, area_m2 / espacamento               # comprimento total no círculo


def calcular_insumos(talhao: dict) -> list[dict]:
    resultado = []
    for nome, tipo, dose, unidade, unidade_total in INSUMOS[talhao["CULTURA"]]:
        if tipo == "POR_HA":
            total = dose * talhao["AREA_HA"]
        else:                                        # mL por metro -> litros
            total = dose * talhao["METROS_LINEARES"] / 1000
        resultado.append({"ID_TALHAO": talhao["ID_TALHAO"], "INSUMO": nome,
                          "TIPO_DOSE": tipo, "DOSE": dose, "UNIDADE": unidade,
                          "QUANTIDADE_TOTAL": round(total, 3), "UNIDADE_TOTAL": unidade_total})
    return resultado


def montar_talhao(id_talhao: int, cultura: str, nome: str, dimensao_1: float,
                  dimensao_2: float | None) -> dict:
    cultura = cultura.lower()
    if cultura not in CULTURAS:
        raise ValueError(f"Cultura inválida: {cultura}. Opções: {', '.join(CULTURAS)}")
    if FORMAS[cultura] == "CIRCULO":
        dimensao_2 = None
    area = calcular_area(cultura, dimensao_1, dimensao_2)
    ruas, metros = calcular_ruas(cultura, dimensao_1, dimensao_2, area)
    return {
        "ID_TALHAO": id_talhao, "NOME": nome.strip(), "CULTURA": cultura,
        "ID_CULTURA": CULTURAS[cultura]["id"], "FORMA": FORMAS[cultura],
        "DIMENSAO_1_M": round(dimensao_1, 2),
        "DIMENSAO_2_M": round(dimensao_2, 2) if dimensao_2 else None,
        "AREA_M2": round(area, 2), "AREA_HA": round(area / 10_000, 4),
        "NUM_RUAS": ruas, "METROS_LINEARES": round(metros, 1),
        "DATA_CADASTRO": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ------------------------------------------------------------- persistência
def carregar() -> None:
    talhoes.clear()
    arquivo = ARQUIVOS["talhoes"]
    if not arquivo.exists():
        return
    with open(arquivo, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            dim2 = float(linha["DIMENSAO_2_M"]) if linha["DIMENSAO_2_M"] else None
            talhao = montar_talhao(int(linha["ID_TALHAO"]), linha["CULTURA"], linha["NOME"],
                                   float(linha["DIMENSAO_1_M"]), dim2)
            talhao["DATA_CADASTRO"] = linha["DATA_CADASTRO"]
            talhoes.append(talhao)


def exportar() -> None:
    ARQUIVOS["talhoes"].parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVOS["talhoes"], "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_TALHAO)
        escritor.writeheader()
        escritor.writerows(talhoes)
    aplicacoes = [i for t in talhoes for i in calcular_insumos(t)]
    for indice, aplicacao in enumerate(aplicacoes, start=1):
        aplicacao["ID_APLICACAO"] = indice
    with open(ARQUIVOS["insumos"], "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_INSUMO)
        escritor.writeheader()
        escritor.writerows(aplicacoes)


def proximo_id() -> int:
    return max((t["ID_TALHAO"] for t in talhoes), default=0) + 1


def buscar(id_talhao: int) -> dict | None:
    for talhao in talhoes:
        if talhao["ID_TALHAO"] == id_talhao:
            return talhao
    return None


# ------------------------------------------------------------------ operações
def adicionar(cultura: str, nome: str, dimensao_1: float, dimensao_2: float | None) -> dict:
    talhao = montar_talhao(proximo_id(), cultura, nome, dimensao_1, dimensao_2)
    talhoes.append(talhao)
    exportar()
    return talhao


def atualizar(id_talhao: int, dimensao_1: float, dimensao_2: float | None) -> dict:
    atual = buscar(id_talhao)
    if atual is None:
        raise ValueError(f"Talhão {id_talhao} não encontrado.")
    novo = montar_talhao(id_talhao, atual["CULTURA"], atual["NOME"], dimensao_1, dimensao_2)
    talhoes[talhoes.index(atual)] = novo
    exportar()
    return novo


def remover(id_talhao: int) -> None:
    atual = buscar(id_talhao)
    if atual is None:
        raise ValueError(f"Talhão {id_talhao} não encontrado.")
    if id_talhao == 1:
        raise ValueError("O talhão 1 recebe os sensores ESP32 (Fase 2) e não pode ser removido.")
    talhoes.remove(atual)
    exportar()


def carregar_exemplo() -> None:
    talhoes.clear()
    for cultura, nome, d1, d2 in EXEMPLOS:
        talhoes.append(montar_talhao(proximo_id(), cultura, nome, d1, d2))
    exportar()


def listar() -> None:
    if not talhoes:
        print("Nenhum talhão cadastrado.")
        return
    print(f"{'ID':>3}  {'Talhão':<24} {'Cultura':<6} {'Forma':<9} {'Área (ha)':>9} "
          f"{'Ruas':>5} {'Metros lineares':>16}")
    for t in talhoes:
        print(f"{t['ID_TALHAO']:>3}  {t['NOME']:<24} {t['CULTURA']:<6} {t['FORMA']:<9} "
              f"{t['AREA_HA']:>9.2f} {t['NUM_RUAS']:>5} {t['METROS_LINEARES']:>16,.1f}")
    print("\nInsumos necessários:")
    for t in talhoes:
        print(f"  {t['NOME']}")
        for i in calcular_insumos(t):
            print(f"    - {i['INSUMO']:<38} {i['DOSE']:>7.1f} {i['UNIDADE']:<6} "
                  f"-> {i['QUANTIDADE_TOTAL']:>10,.2f} {i['UNIDADE_TOTAL']}")
    area_total = sum(t["AREA_HA"] for t in talhoes)
    print(f"\nÁrea total plantada: {area_total:.2f} ha em {len(talhoes)} talhões.")


# ----------------------------------------------------------- menu interativo
def ler_float(mensagem: str) -> float:
    while True:
        try:
            valor = float(input(mensagem).replace(",", "."))
            if valor > 0:
                return valor
            print("Informe um valor maior que zero.")
        except ValueError:
            print("Valor inválido, tente novamente.")


def ler_cultura() -> str:
    while True:
        opcao = input("Cultura (1 = Soja | 2 = Milho): ").strip()
        if opcao in {"1", "2"}:
            return "soja" if opcao == "1" else "milho"
        print("Opção inválida.")


def ler_dimensoes(cultura: str) -> tuple[float, float | None]:
    if FORMAS[cultura] == "RETANGULO":
        return ler_float("Comprimento (m): "), ler_float("Largura (m): ")
    return ler_float("Raio do pivô (m): "), None


def menu() -> None:
    opcoes = {"1": "Entrada de dados (novo talhão)", "2": "Saída de dados (listar)",
              "3": "Atualizar talhão", "4": "Deletar talhão",
              "5": "Carregar talhões de exemplo", "0": "Sair"}
    while True:
        print("\n===== FarmTech Solutions - Fase 1: Plantio e Insumos =====")
        for chave, texto in opcoes.items():
            print(f"  {chave} - {texto}")
        escolha = input("Escolha: ").strip()
        try:
            if escolha == "1":
                cultura = ler_cultura()
                nome = input("Nome do talhão: ").strip() or f"Talhão {proximo_id()}"
                d1, d2 = ler_dimensoes(cultura)
                t = adicionar(cultura, nome, d1, d2)
                print(f"Talhão {t['ID_TALHAO']} cadastrado: {t['AREA_HA']:.2f} ha.")
            elif escolha == "2":
                listar()
            elif escolha == "3":
                listar()
                t = buscar(int(input("ID do talhão: ")))
                if t is None:
                    print("Talhão não encontrado.")
                    continue
                d1, d2 = ler_dimensoes(t["CULTURA"])
                atualizar(t["ID_TALHAO"], d1, d2)
                print("Talhão atualizado.")
            elif escolha == "4":
                listar()
                remover(int(input("ID do talhão a remover: ")))
                print("Talhão removido.")
            elif escolha == "5":
                carregar_exemplo()
                print("Talhões de exemplo carregados.")
            elif escolha == "0":
                print("Dados salvos em", ARQUIVOS["talhoes"].name, "- até logo!")
                break
            else:
                print("Opção inválida.")
        except ValueError as erro:
            print(f"[ERRO] {erro}")


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="FarmTech Fase 1 - plantio e insumos")
    parser.add_argument("--exemplo", action="store_true", help="carrega os talhões de exemplo")
    parser.add_argument("--listar", action="store_true", help="lista talhões e insumos")
    parser.add_argument("--adicionar", nargs="+", metavar="VALOR",
                        help="CULTURA NOME DIM1 [DIM2]")
    parser.add_argument("--atualizar", nargs="+", metavar="VALOR", help="ID DIM1 [DIM2]")
    parser.add_argument("--remover", type=int, metavar="ID")
    parser.add_argument("--menu", action="store_true", help="abre o menu interativo (padrão)")
    args = parser.parse_args()

    carregar()
    try:
        if args.exemplo:
            carregar_exemplo()
            print(f"{len(talhoes)} talhões de exemplo carregados e exportados.")
        elif args.adicionar:
            cultura, nome, *dims = args.adicionar
            t = adicionar(cultura, nome, float(dims[0]), float(dims[1]) if len(dims) > 1 else None)
            print(f"Talhão {t['ID_TALHAO']} ({t['NOME']}) cadastrado com {t['AREA_HA']:.2f} ha.")
        elif args.atualizar:
            id_talhao, *dims = args.atualizar
            t = atualizar(int(id_talhao), float(dims[0]),
                          float(dims[1]) if len(dims) > 1 else None)
            print(f"Talhão {t['ID_TALHAO']} atualizado: {t['AREA_HA']:.2f} ha.")
        elif args.remover:
            remover(args.remover)
            print(f"Talhão {args.remover} removido.")
        elif not args.listar:
            menu()
            return 0
    except (ValueError, IndexError) as erro:
        print(f"[ERRO] {erro}")
        return 1
    listar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
