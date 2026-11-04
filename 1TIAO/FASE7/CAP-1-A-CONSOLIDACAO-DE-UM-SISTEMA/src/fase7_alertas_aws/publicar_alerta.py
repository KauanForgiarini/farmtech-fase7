"""
FarmTech Solutions - Fase 7: publicador de alertas (cliente do serviço na AWS).

Monta o evento com as últimas leituras dos sensores (Fases 1/2, já com as
previsões da Fase 4) e as detecções da visão computacional (Fase 6), lidos do
banco da Fase 3, e o entrega ao serviço de mensageria na AWS:

  --modo s3      grava o JSON no bucket S3 -> gatilho -> Lambda -> SNS (assíncrono)
  --modo lambda  invoca a função Lambda, que avalia as regras e publica no SNS
  --modo sns     avalia localmente e publica direto no tópico SNS
  --modo local   apenas avalia e mostra a mensagem (sem AWS; útil para testes)
  --modo auto    lambda se a AWS estiver configurada; caso contrário local

Uso:
    python src/fase7_alertas_aws/publicar_alerta.py --modo auto
    python src/fase7_alertas_aws/publicar_alerta.py --modo lambda --origem visao
    python src/fase7_alertas_aws/publicar_alerta.py --modo sns --teste-critico
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from farmtech_core.config import ARQUIVOS, configurar_saida
from fase7_alertas_aws import aws_config
from fase7_alertas_aws.lambda_alertas import regras_alerta as regras

COLUNAS = ["ID_ALERTA", "DATA_HORA", "ORIGEM", "CODIGO", "SEVERIDADE", "TITULO",
           "LOCAL_ALERTA", "EVIDENCIA", "ACAO_CORRETIVA", "RESPONSAVEL", "OCORRENCIAS",
           "CANAL", "STATUS_ENVIO", "MESSAGE_ID"]

SQL_LEITURAS = """
SELECT L.ID_LEITURA, L.DATA_HORA, T.NOME AS TALHAO, L.N_PRESENTE, L.P_PRESENTE,
       L.K_PRESENTE, L.PH_SOLO, L.UMIDADE_SOLO_PCT, L.TEMPERATURA_C, L.CHUVA_PREVISTA_MM,
       L.BOMBA_LIGADA, L.MOTIVO_DECISAO, P.VOLUME_IRRIGACAO_L
FROM LEITURA_SENSOR L
JOIN TALHAO T ON T.ID_TALHAO = L.ID_TALHAO
LEFT JOIN PREVISAO_ML P ON P.ID_LEITURA = L.ID_LEITURA
ORDER BY L.ID_LEITURA
"""
SQL_DETECCOES = """
SELECT DATA_HORA, LOCAL_CAMERA, IMAGEM, CLASSE, CONFIANCA
FROM DETECCAO_VISAO ORDER BY ID_DETECCAO
"""


def _registros(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def coletar_dados(ultimas: int) -> tuple[list[dict], list[dict], str]:
    """Lê do banco da Fase 3; sem banco, lê os CSVs das fases."""
    try:
        from fase3_banco_dados.banco import Banco

        with Banco() as banco:
            if banco.tabelas_existem():
                leituras = banco.dataframe(SQL_LEITURAS)
                deteccoes = banco.dataframe(SQL_DETECCOES)
                return (_registros(leituras.tail(ultimas)), _registros(deteccoes),
                        banco.descricao)
    except Exception as erro:
        print(f"[AVISO] Banco indisponível ({erro}); usando os arquivos CSV.")
    leituras, deteccoes = [], []
    if ARQUIVOS["leituras"].exists():
        df = pd.read_csv(ARQUIVOS["leituras"])
        if ARQUIVOS["previsoes"].exists():
            df = df.merge(pd.read_csv(ARQUIVOS["previsoes"])[["ID_LEITURA", "VOLUME_IRRIGACAO_L"]],
                          on="ID_LEITURA", how="left")
        df["TALHAO"] = "Talhão 1 - Soja Norte"
        leituras = _registros(df.tail(ultimas))
    if ARQUIVOS["deteccoes"].exists():
        df = pd.read_csv(ARQUIVOS["deteccoes"])
        deteccoes = _registros(df)
    return leituras, deteccoes, "arquivos CSV"


def payload_teste_critico() -> dict:
    """Leitura sintética para demonstrar um alerta crítico (vídeo / teste do SNS)."""
    return {"origem": "sensores", "leituras": [{
        "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "talhao": "Talhão 1 - Soja Norte", "umidade": 34.0, "ph": 4.8, "temperatura": 36.5,
        "chuva_mm": 0.0, "n": 0, "p": 0, "k": 0, "bomba": 0, "motivo": "ph_fora_faixa"}]}


def enviar(modo: str, payloads: list[dict], alertas: list[dict], config: dict) -> list[dict]:
    """Entrega os payloads à AWS. Devolve o status de cada envio."""
    if modo == "local":
        return [{"canal": "local", "status": "SIMULADO", "message_id": ""}]
    sessao = aws_config.sessao(config["regiao"])
    agora = datetime.now().strftime("%Y%m%d-%H%M%S")
    envios = []
    if modo == "s3":
        s3 = sessao.client("s3")
        for payload in payloads:
            chave = f"{payload['origem']}/{agora}-{payload['origem']}.json"
            s3.put_object(Bucket=config["bucket"], Key=chave, ContentType="application/json",
                          Body=json.dumps(payload, ensure_ascii=False, default=str).encode())
            envios.append({"canal": "s3", "status": "ENVIADO_S3",
                           "message_id": f"s3://{config['bucket']}/{chave}"})
    elif modo == "lambda":
        resposta = sessao.client("lambda").invoke(
            FunctionName=config["funcao_lambda"], InvocationType="RequestResponse",
            Payload=json.dumps({"origem": "+".join(p["origem"] for p in payloads),
                                "leituras": [l for p in payloads for l in p.get("leituras", [])],
                                "deteccoes": [d for p in payloads for d in p.get("deteccoes", [])]},
                               ensure_ascii=False, default=str).encode())
        retorno = json.loads(resposta["Payload"].read() or b"{}")
        print("Resposta da Lambda:", json.dumps(retorno, ensure_ascii=False))
        status = "ENVIADO" if retorno.get("status") == "enviado" else retorno.get("status", "ERRO")
        envios.append({"canal": "lambda+sns", "status": status.upper(),
                       "message_id": retorno.get("message_id", "")})
    elif modo == "sns":
        mensagem = regras.montar_mensagem(alertas)
        resposta = sessao.client("sns").publish(
            TopicArn=config["topic_arn"], Subject=mensagem["assunto"],
            MessageStructure="json",
            Message=json.dumps({"default": mensagem["corpo"], "email": mensagem["corpo"],
                                "sms": mensagem["sms"]}, ensure_ascii=False),
            MessageAttributes={"severidade": {"DataType": "String",
                                              "StringValue": mensagem["severidade"]},
                               "origem": {"DataType": "String", "StringValue": "dashboard"}})
        envios.append({"canal": "sns", "status": "ENVIADO", "message_id": resposta["MessageId"]})
    return envios


def registrar(alertas: list[dict], envio: dict) -> None:
    arquivo = ARQUIVOS["alertas"]
    ultimo = 0
    if arquivo.exists():
        with open(arquivo, encoding="utf-8") as f:
            ultimo = max((int(l["ID_ALERTA"]) for l in csv.DictReader(f)), default=0)
    novo = not arquivo.exists()
    with open(arquivo, "a", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo:
            escritor.writeheader()
        for i, a in enumerate(alertas, start=1):
            escritor.writerow({
                "ID_ALERTA": ultimo + i,
                "DATA_HORA": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ORIGEM": a["origem"], "CODIGO": a["codigo"], "SEVERIDADE": a["severidade"],
                "TITULO": a["titulo"][:150], "LOCAL_ALERTA": a["local"][:60],
                "EVIDENCIA": a["evidencia"][:500], "ACAO_CORRETIVA": a["acao"][:800],
                "RESPONSAVEL": a["responsavel"], "OCORRENCIAS": a["ocorrencias"],
                "CANAL": envio["canal"], "STATUS_ENVIO": envio["status"],
                "MESSAGE_ID": envio["message_id"][:100]})


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Serviço de alertas FarmTech (Fase 7)")
    parser.add_argument("--modo", choices=["auto", "local", "s3", "lambda", "sns"], default="auto")
    parser.add_argument("--origem", choices=["todos", "sensores", "visao"], default="todos")
    parser.add_argument("--ultimas", type=int, default=6, help="leituras recentes avaliadas")
    parser.add_argument("--severidade-minima", default="MEDIO",
                        choices=regras.SEVERIDADES)
    parser.add_argument("--teste-critico", action="store_true",
                        help="envia uma leitura sintética crítica (demonstração)")
    args = parser.parse_args()

    config = aws_config.carregar()
    modo = args.modo
    if modo == "auto":
        configurado = ARQUIVOS["aws_config"].exists() and bool(config["topic_arn"])
        valido, detalhe = aws_config.credenciais_validas(config["regiao"]) if configurado \
            else (False, "execute deploy_aws.py para criar os recursos")
        modo = "lambda" if valido else "local"
        print(f"Modo automático: {modo} ({detalhe})")

    if args.teste_critico:
        payloads, fonte = [payload_teste_critico()], "leitura sintética de teste"
    else:
        leituras, deteccoes, fonte = coletar_dados(args.ultimas)
        payloads = []
        if args.origem in {"todos", "sensores"} and leituras:
            payloads.append({"origem": "sensores", "leituras": leituras})
        if args.origem in {"todos", "visao"} and deteccoes:
            payloads.append({"origem": "visao", "deteccoes": deteccoes})
    if not payloads:
        print("Nenhum dado para avaliar. Execute antes: python farmtech.py fase2 / fase6")
        return 1

    alertas = []
    for payload in payloads:
        alertas.extend(regras.avaliar_payload(payload, ultimas_leituras=args.ultimas))
    alertas = regras.filtrar_severidade(alertas, args.severidade_minima)
    print(f"Fonte dos dados: {fonte} | {len(alertas)} alerta(s) acima de "
          f"{args.severidade_minima}")
    if not alertas:
        print("Nenhuma ação corretiva necessária no momento.")
        return 0

    mensagem = regras.montar_mensagem(alertas)
    print(f"\nAssunto: {mensagem['assunto']}\n\n{mensagem['corpo']}\n\nSMS: {mensagem['sms']}\n")
    try:
        envios = enviar(modo, payloads, alertas, config)
    except Exception as erro:
        print(f"[ERRO] Falha ao enviar para a AWS ({type(erro).__name__}: {erro}).")
        print("Confira as credenciais do Learner Lab em ~/.aws/credentials (expiram a cada sessão).")
        registrar(alertas, {"canal": modo, "status": "FALHA", "message_id": ""})
        return 1
    for envio in envios:
        print(f"Envio: canal={envio['canal']} status={envio['status']} id={envio['message_id']}")
    registrar(alertas, envios[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
