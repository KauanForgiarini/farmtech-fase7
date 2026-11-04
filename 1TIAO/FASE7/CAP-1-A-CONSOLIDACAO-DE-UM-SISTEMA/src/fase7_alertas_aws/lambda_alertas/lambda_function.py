"""
FarmTech Solutions - Função AWS Lambda "farmtech-alertas" (Fase 7).

Fluxo:
  1. Recebe um evento com leituras de sensores e/ou detecções de visão:
       - invocação direta (boto3 lambda.invoke ou botão "Testar" do console);
       - evento do Amazon S3 (arquivo JSON enviado em sensores/ ou visao/);
       - API Gateway (campo "body" com o JSON).
  2. Aplica as regras agronômicas e de segurança (regras_alerta.py).
  3. Publica no tópico Amazon SNS os alertas com as ações corretivas.
     O SNS entrega por e-mail (texto completo) e por SMS (texto curto).

Variáveis de ambiente:
  TOPIC_ARN          ARN do tópico SNS de alertas (obrigatória para envio)
  SEVERIDADE_MINIMA  INFO | MEDIO | ALTO | CRITICO (padrão: MEDIO)
  NOME_FAZENDA       nome exibido no assunto do e-mail
"""

import json
import os
import urllib.parse

import boto3

try:  # importação como pacote (testes locais) ou como módulo de topo (Lambda)
    from . import regras_alerta as regras
except ImportError:  # pragma: no cover - caminho usado dentro da AWS
    import regras_alerta as regras

TOPIC_ARN = os.environ.get("TOPIC_ARN", "")
SEVERIDADE_MINIMA = os.environ.get("SEVERIDADE_MINIMA", "MEDIO")
NOME_FAZENDA = os.environ.get("NOME_FAZENDA", "Fazenda FarmTech")

_clientes = {}


def _cliente(servico):
    """Cria o cliente boto3 uma única vez por contêiner (reaproveitado entre invocações)."""
    if servico not in _clientes:
        _clientes[servico] = boto3.client(servico)
    return _clientes[servico]


def _ler_objeto_s3(bucket, chave):
    resposta = _cliente("s3").get_object(Bucket=bucket, Key=chave)
    return json.loads(resposta["Body"].read().decode("utf-8"))


def extrair_payloads(event):
    """Normaliza os diferentes tipos de evento em uma lista de payloads."""
    if isinstance(event, dict) and event.get("Records"):
        payloads = []
        for registro in event["Records"]:
            if "s3" not in registro:
                continue
            bucket = registro["s3"]["bucket"]["name"]
            chave = urllib.parse.unquote_plus(registro["s3"]["object"]["key"])
            payload = _ler_objeto_s3(bucket, chave)
            payload.setdefault("fonte", f"s3://{bucket}/{chave}")
            payloads.append(payload)
        return payloads
    if isinstance(event, dict) and isinstance(event.get("body"), str):
        return [json.loads(event["body"])]
    return [event or {}]


def publicar(alertas, origem):
    mensagem = regras.montar_mensagem(alertas, NOME_FAZENDA)
    resposta = _cliente("sns").publish(
        TopicArn=TOPIC_ARN,
        Subject=mensagem["assunto"],
        # Mensagem por protocolo: e-mail recebe o relatório, SMS recebe o resumo
        MessageStructure="json",
        Message=json.dumps({
            "default": mensagem["corpo"],
            "email": mensagem["corpo"],
            "sms": mensagem["sms"],
        }, ensure_ascii=False),
        # Atributos permitem filtrar assinaturas (ex.: SMS só para CRITICO/ALTO)
        MessageAttributes={
            "severidade": {"DataType": "String", "StringValue": mensagem["severidade"]},
            "origem": {"DataType": "String", "StringValue": origem},
        },
    )
    return resposta["MessageId"], mensagem


def lambda_handler(event, context):
    payloads = extrair_payloads(event)
    alertas = []
    origens = set()
    for payload in payloads:
        alertas.extend(regras.avaliar_payload(payload))
        origens.add(payload.get("origem", "desconhecida"))
    alertas = regras.filtrar_severidade(alertas, SEVERIDADE_MINIMA)
    origem = "+".join(sorted(origens)) or "desconhecida"

    print(json.dumps({"payloads": len(payloads), "alertas": len(alertas),
                      "origem": origem}, ensure_ascii=False))
    if not alertas:
        return {"status": "sem_alertas", "alertas": 0, "origem": origem}
    if not TOPIC_ARN:
        return {"status": "erro", "detalhe": "TOPIC_ARN não configurado",
                "alertas": len(alertas)}

    message_id, mensagem = publicar(alertas, origem)
    return {
        "status": "enviado",
        "message_id": message_id,
        "severidade": mensagem["severidade"],
        "assunto": mensagem["assunto"],
        "alertas": len(alertas),
        "codigos": [a["codigo"] for a in alertas],
        "origem": origem,
    }
