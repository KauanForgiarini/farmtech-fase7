"""
FarmTech Solutions - Regras agronômicas e de alerta (fonte única de limites).

Este módulo concentra:
  * os limites agronômicos usados em todo o sistema (firmware, simulador,
    banco, dashboard e nuvem);
  * a decisão de irrigação, idêntica à função deveIrrigar() do ESP32 (Fase 2);
  * as regras que transformam leituras de sensores (Fases 1/2) e detecções de
    visão computacional (Fase 6) em alertas com ações corretivas (Fase 7);
  * a montagem da mensagem enviada pelo Amazon SNS (e-mail e SMS).

Usa apenas a biblioteca padrão para poder ser empacotado diretamente na
função AWS Lambda, sem camadas (layers) extras.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

# ---------------------------------------------------------------------------
# Limites agronômicos (Embrapa Soja / firmware da Fase 2)
# ---------------------------------------------------------------------------
LIMITES = {
    "umidade_min": 60.0,        # abaixo disso o solo está seco -> irrigar
    "umidade_critica": 40.0,    # déficit hídrico severo
    "umidade_max": 80.0,        # solo saturado -> não irrigar
    "umidade_alvo": 70.0,       # meta após a irrigação
    "ph_irrigacao_min": 5.0,    # firmware: fora desta faixa a bomba não liga
    "ph_irrigacao_max": 7.5,
    "ph_ideal_min": 5.5,        # faixa ideal para soja (Embrapa)
    "ph_ideal_max": 7.0,
    "chuva_limiar_mm": 5.0,     # chuva prevista que suspende a irrigação
    "chuva_forte_mm": 20.0,     # chuva que exige adiar pulverização/adubação
    "temperatura_max": 35.0,    # estresse térmico
    "n_min_kgha": 80.0,         # abaixo disso o nutriente é "ausente"
    "p_min_kgha": 60.0,
    "k_min_kgha": 80.0,
    "confianca_visao": 0.50,    # confiança mínima para considerar a detecção
}

# Culturas suportadas (também carregadas na tabela CULTURA da Fase 3)
CULTURAS = {
    "soja": {"id": 1, "nome": "Soja", "ph_min": 5.5, "ph_max": 7.0,
             "umidade_min": 60.0, "umidade_max": 80.0, "espacamento_m": 0.50},
    "milho": {"id": 2, "nome": "Milho", "ph_min": 5.5, "ph_max": 7.0,
              "umidade_min": 55.0, "umidade_max": 80.0, "espacamento_m": 0.80},
}

SEVERIDADES = ["INFO", "MEDIO", "ALTO", "CRITICO"]

MOTIVOS = {
    "chuva_prevista": "Chuva prevista - irrigação suspensa",
    "solo_saturado": "Solo saturado - sem necessidade de irrigar",
    "ph_fora_faixa": "pH fora da faixa - corrigir o solo antes de irrigar",
    "umidade_adequada": "Umidade adequada - irrigação não necessária",
    "irrigando": "Solo seco com nutrientes - irrigando",
    "sem_nutrientes": "Solo seco sem P e K - adubar antes de irrigar",
}


# ---------------------------------------------------------------------------
# Decisão de irrigação (mesma ordem de testes do firmware ESP32)
# ---------------------------------------------------------------------------
def decidir_irrigacao(umidade: float, ph: float, chuva_mm: float,
                      p_presente: bool, k_presente: bool,
                      limites: dict = LIMITES) -> tuple[bool, str]:
    """Replica deveIrrigar() do firmware. Retorna (ligar_bomba, motivo)."""
    if chuva_mm >= limites["chuva_limiar_mm"]:
        return False, "chuva_prevista"
    if umidade >= limites["umidade_max"]:
        return False, "solo_saturado"
    if ph < limites["ph_irrigacao_min"] or ph > limites["ph_irrigacao_max"]:
        return False, "ph_fora_faixa"
    if umidade >= limites["umidade_min"]:
        return False, "umidade_adequada"
    if p_presente or k_presente:
        return True, "irrigando"
    return False, "sem_nutrientes"


def estimar_volume_irrigacao(umidade: float, temperatura: float,
                             limites: dict = LIMITES) -> float:
    """Estimativa simples (L/m²) para levar o solo à umidade alvo (regra da Fase 4)."""
    deficit = max(0.0, limites["umidade_alvo"] - umidade)
    fator_temp = 1 + (temperatura - 25) * 0.02
    return round(max(0.0, deficit * 0.15 * fator_temp), 2)


# ---------------------------------------------------------------------------
# Construção de alertas
# ---------------------------------------------------------------------------
def _alerta(codigo, origem, severidade, titulo, evidencia, acao, responsavel,
            local, data_hora):
    return {
        "codigo": codigo,
        "origem": origem,
        "severidade": severidade,
        "titulo": titulo,
        "evidencia": evidencia,
        "acao": acao,
        "responsavel": responsavel,
        "local": local,
        "data_hora": data_hora,
        "ocorrencias": 1,
    }


def _bool(valor) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() in {"1", "true", "sim", "s", "yes"}
    return bool(valor)


def normalizar_leitura(leitura: dict) -> dict:
    """Aceita tanto o formato do CSV/banco (MAIÚSCULAS) quanto o JSON do ESP32."""
    def pegar(*chaves, padrao=None):
        for chave in chaves:
            if chave in leitura and leitura[chave] not in (None, ""):
                return leitura[chave]
        return padrao

    return {
        "data_hora": str(pegar("data_hora", "DATA_HORA", "timestamp", padrao="")),
        "talhao": str(pegar("talhao", "TALHAO", "NOME_TALHAO", padrao="Talhão 1")),
        "umidade": float(pegar("umidade", "UMIDADE_SOLO_PCT", padrao=0.0)),
        "ph": float(pegar("ph", "PH_SOLO", padrao=7.0)),
        "temperatura": float(pegar("temperatura", "TEMPERATURA_C", padrao=25.0)),
        "chuva_mm": float(pegar("chuva_mm", "CHUVA_PREVISTA_MM", padrao=0.0)),
        "n": _bool(pegar("n", "N_PRESENTE", padrao=1)),
        "p": _bool(pegar("p", "P_PRESENTE", padrao=1)),
        "k": _bool(pegar("k", "K_PRESENTE", padrao=1)),
        "bomba": _bool(pegar("bomba", "BOMBA_LIGADA", padrao=0)),
        "motivo": str(pegar("motivo", "MOTIVO_DECISAO", padrao="")),
        "volume_previsto": pegar("volume_previsto", "VOLUME_IRRIGACAO_L"),
    }


def avaliar_leitura(leitura: dict, limites: dict = LIMITES) -> list[dict]:
    """Aplica as regras de campo a uma leitura de sensores."""
    r = normalizar_leitura(leitura)
    alertas = []
    local, quando = r["talhao"], r["data_hora"]
    base = (f"umidade {r['umidade']:.1f}% | pH {r['ph']:.2f} | "
            f"temp. {r['temperatura']:.1f} °C | chuva prevista {r['chuva_mm']:.1f} mm | "
            f"bomba {'LIGADA' if r['bomba'] else 'DESLIGADA'}")

    volume = r["volume_previsto"]
    if volume in (None, ""):
        volume = estimar_volume_irrigacao(r["umidade"], r["temperatura"], limites)
        fonte_volume = "estimativa por regra"
    else:
        volume = round(float(volume), 2)
        fonte_volume = "modelo preditivo da Fase 4"

    # 1. Umidade do solo
    if r["umidade"] < limites["umidade_critica"]:
        if r["bomba"]:
            acao = ("Bomba já está ligada, mas a umidade continua crítica: verificar vazão, "
                    "pressão da linha e entupimento de aspersores/gotejadores.")
        else:
            acao = (f"Acionar a irrigação imediatamente: aplicar cerca de {volume:.2f} L/m² "
                    f"({fonte_volume}) para levar o solo a {limites['umidade_alvo']:.0f}%.")
            if r["motivo"] == "sem_nutrientes":
                acao += " A irrigação está bloqueada por falta de P e K: adubar primeiro."
            elif r["motivo"] == "ph_fora_faixa":
                acao += " A irrigação está bloqueada pelo pH: corrigir o solo primeiro."
        alertas.append(_alerta("UMIDADE_CRITICA", "sensores", "CRITICO",
                               "Déficit hídrico severo no solo", base, acao,
                               "Operador de irrigação", local, quando))
    elif r["umidade"] < limites["umidade_min"] and r["motivo"] == "sem_nutrientes":
        alertas.append(_alerta(
            "IRRIGACAO_BLOQUEADA_NPK", "sensores", "ALTO",
            "Solo seco e irrigação bloqueada por falta de P e K", base,
            "Aplicar adubação fosfatada e potássica (ex.: formulado 00-20-20, dose conforme "
            "análise de solo). Após a adubação a irrigação é liberada automaticamente.",
            "Agrônomo responsável", local, quando))
    elif r["umidade"] >= limites["umidade_max"]:
        alertas.append(_alerta(
            "SOLO_SATURADO", "sensores", "MEDIO", "Solo saturado", base,
            "Manter a bomba desligada, verificar drenagem e possíveis vazamentos, evitar tráfego "
            "de máquinas (compactação) e reforçar o monitoramento de doenças fúngicas.",
            "Operador de irrigação", local, quando))

    # 2. pH do solo
    bloqueia = r["ph"] < limites["ph_irrigacao_min"] or r["ph"] > limites["ph_irrigacao_max"]
    if r["ph"] < limites["ph_ideal_min"]:
        alertas.append(_alerta(
            "PH_ACIDO", "sensores", "CRITICO" if bloqueia else "ALTO",
            f"Solo ácido (pH {r['ph']:.2f})", base,
            "Realizar calagem com calcário dolomítico (dose pela análise de solo; referência de "
            "2 a 3 t/ha) e reavaliar o pH em 60 a 90 dias.",
            "Agrônomo responsável", local, quando))
    elif r["ph"] > limites["ph_ideal_max"]:
        alertas.append(_alerta(
            "PH_ALCALINO", "sensores", "CRITICO" if bloqueia else "ALTO",
            f"Solo alcalino (pH {r['ph']:.2f})", base,
            "Suspender a calagem, aplicar enxofre elementar ou gesso conforme análise e preferir "
            "fertilizantes de reação ácida (ex.: sulfato de amônio).",
            "Agrônomo responsável", local, quando))

    # 3. Nitrogênio
    if not r["n"]:
        alertas.append(_alerta(
            "NITROGENIO_BAIXO", "sensores", "MEDIO", "Nitrogênio abaixo do ideal", base,
            "Na soja, verificar a nodulação e a inoculação com Bradyrhizobium; no milho, aplicar "
            "nitrogênio em cobertura (ureia) no estádio V4-V6.",
            "Agrônomo responsável", local, quando))

    # 4. Clima
    if r["temperatura"] > limites["temperatura_max"]:
        alertas.append(_alerta(
            "ESTRESSE_TERMICO", "sensores", "MEDIO",
            f"Estresse térmico ({r['temperatura']:.1f} °C)", base,
            "Priorizar a irrigação no início da manhã ou no fim da tarde e monitorar o "
            "abortamento de flores e vagens.",
            "Operador de irrigação", local, quando))
    if r["chuva_mm"] >= limites["chuva_forte_mm"]:
        alertas.append(_alerta(
            "CHUVA_FORTE", "sensores", "MEDIO",
            f"Chuva forte prevista ({r['chuva_mm']:.1f} mm)", base,
            "Adiar pulverizações e adubação de cobertura (risco de lavagem e lixiviação) e "
            "conferir terraços e canais de drenagem.",
            "Gerente da fazenda", local, quando))
    return alertas


CLASSES_VISAO = {
    # YOLO da Fase 6 (rótulos em português) e Amazon Rekognition (Ir Além 1)
    "pessoa": "pessoa", "person": "pessoa", "human": "pessoa",
    "carro": "carro", "car": "carro", "vehicle": "carro", "truck": "carro",
    "automobile": "carro", "pickup truck": "carro", "tractor": "carro",
}


def avaliar_deteccao(deteccao: dict, limites: dict = LIMITES) -> list[dict]:
    """Converte uma detecção de visão computacional em alerta de segurança."""
    classe = CLASSES_VISAO.get(str(deteccao.get("classe", deteccao.get("CLASSE", ""))).lower())
    confianca = float(deteccao.get("confianca", deteccao.get("CONFIANCA", 0.0)))
    if classe is None or confianca < limites["confianca_visao"]:
        return []
    local = str(deteccao.get("local") or deteccao.get("LOCAL_CAMERA")
                or deteccao.get("LOCAL") or "Câmera da fazenda")
    quando = str(deteccao.get("data_hora", deteccao.get("DATA_HORA", "")))
    imagem = str(deteccao.get("imagem", deteccao.get("IMAGEM", "")))
    evidencia = f"{classe} detectado(a) com confiança {confianca:.0%} | imagem {imagem}"

    if classe == "pessoa":
        return [_alerta(
            "PESSOA_DETECTADA", "visao", "ALTO", f"Pessoa detectada em {local}", evidencia,
            "Confirmar pela câmera se é um funcionário autorizado. Se houver aplicação de "
            "defensivos no talhão, suspender a pulverização e respeitar o intervalo de reentrada. "
            "Acionar a equipe de segurança se a pessoa não for identificada.",
            "Equipe de segurança", local, quando)]
    return [_alerta(
        "VEICULO_DETECTADO", "visao", "MEDIO", f"Veículo detectado em {local}", evidencia,
        "Conferir se o veículo consta na agenda de entradas (fornecedores, colheita, "
        "transporte), registrar placa e horário e liberar o acesso somente após a conferência.",
        "Portaria", local, quando)]


# ---------------------------------------------------------------------------
# Avaliação de lotes (o que chega ao Lambda)
# ---------------------------------------------------------------------------
def _consolidar(alertas: list[dict]) -> list[dict]:
    """Agrupa alertas repetidos (mesmo código e local), mantendo o mais recente."""
    grupos: dict[tuple, dict] = {}
    for alerta in alertas:
        chave = (alerta["codigo"], alerta["local"])
        if chave not in grupos:
            grupos[chave] = dict(alerta)
            continue
        atual = grupos[chave]
        ocorrencias = atual["ocorrencias"] + 1
        if alerta["data_hora"] >= atual["data_hora"]:
            atual.update(alerta)
        atual["ocorrencias"] = ocorrencias
    return sorted(grupos.values(),
                  key=lambda a: (-SEVERIDADES.index(a["severidade"]), a["codigo"]))


def avaliar_payload(payload: dict, ultimas_leituras: int = 6) -> list[dict]:
    """
    Avalia um evento enviado ao serviço de alertas.

    Formatos aceitos:
      {"origem": "sensores", "leituras": [...]}   (Fases 1/2 via banco da Fase 3)
      {"origem": "visao", "deteccoes": [...]}     (Fase 6 ou Rekognition)
    Um mesmo payload pode trazer as duas listas.
    Para sensores, apenas as últimas N leituras são consideradas (estado atual).
    """
    alertas: list[dict] = []
    leituras = list(payload.get("leituras", []))
    if leituras and ultimas_leituras:
        leituras = leituras[-ultimas_leituras:]
    for leitura in leituras:
        alertas.extend(avaliar_leitura(leitura))
    for deteccao in payload.get("deteccoes", []):
        alertas.extend(avaliar_deteccao(deteccao))
    return _consolidar(alertas)


def filtrar_severidade(alertas: list[dict], minima: str = "MEDIO") -> list[dict]:
    corte = SEVERIDADES.index(minima.upper()) if minima.upper() in SEVERIDADES else 0
    return [a for a in alertas if SEVERIDADES.index(a["severidade"]) >= corte]


def severidade_maxima(alertas: list[dict]) -> str:
    if not alertas:
        return "INFO"
    return max((a["severidade"] for a in alertas), key=SEVERIDADES.index)


# ---------------------------------------------------------------------------
# Mensagem SNS
# ---------------------------------------------------------------------------
def _ascii(texto: str) -> str:
    """O assunto do e-mail no SNS aceita apenas ASCII (máx. 100 caracteres)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.split())


def montar_mensagem(alertas: list[dict], fazenda: str = "Fazenda FarmTech") -> dict:
    """Retorna assunto (ASCII), corpo do e-mail e texto curto para SMS."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    sev = severidade_maxima(alertas)
    criticos = sum(1 for a in alertas if a["severidade"] == "CRITICO")
    assunto = _ascii(f"[FarmTech][{sev}] {len(alertas)} alerta(s) - {fazenda}")[:99]

    linhas = [
        f"FarmTech Solutions - Central de Alertas ({fazenda})",
        f"Gerado em {agora} | Severidade máxima: {sev} | Alertas: {len(alertas)}",
        "=" * 64,
    ]
    for i, a in enumerate(alertas, start=1):
        repeticao = f" (repetido {a['ocorrencias']}x)" if a["ocorrencias"] > 1 else ""
        linhas += [
            f"{i}. [{a['severidade']}] {a['titulo']}{repeticao}",
            f"   Local: {a['local']} | Origem: {a['origem']} | Registro: {a['data_hora']}",
            f"   Evidência: {a['evidencia']}",
            f"   AÇÃO CORRETIVA: {a['acao']}",
            f"   Responsável: {a['responsavel']}",
            "-" * 64,
        ]
    linhas += [
        "Mensagem automática do serviço de alertas FarmTech (AWS Lambda + Amazon SNS).",
        "Dados: sensores ESP32 (Fase 2), banco de dados (Fase 3), modelos (Fase 4) "
        "e visão computacional YOLO (Fase 6).",
    ]

    principal = alertas[0] if alertas else None
    sms = f"FarmTech {sev}: {len(alertas)} alerta(s)"
    if criticos:
        sms += f", {criticos} critico(s)"
    if principal:
        sms += f". {principal['titulo']} em {principal['local']}. {principal['acao']}"
    return {"assunto": assunto, "corpo": "\n".join(linhas), "sms": _ascii(sms)[:300],
            "severidade": sev}
