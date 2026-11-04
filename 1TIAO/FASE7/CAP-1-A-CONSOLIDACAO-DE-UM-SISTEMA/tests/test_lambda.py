"""Testes da função Lambda com clientes AWS falsos (sem acessar a nuvem)."""

import io
import json

from fase7_alertas_aws.lambda_alertas import lambda_function


class SNSFalso:
    def __init__(self):
        self.publicadas = []

    def publish(self, **kwargs):
        self.publicadas.append(kwargs)
        return {"MessageId": "msg-123"}


class S3Falso:
    def __init__(self, objetos):
        self.objetos = objetos

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(json.dumps(self.objetos[Key]).encode())}


EVENTO_CRITICO = {"origem": "sensores", "leituras": [{
    "data_hora": "2026-11-04 10:00:00", "talhao": "Talhão 1", "umidade": 30, "ph": 4.6,
    "temperatura": 37, "chuva_mm": 0, "n": 0, "p": 0, "k": 0, "bomba": 0, "motivo": "ph_fora_faixa"}]}


def preparar(monkeypatch, objetos=None):
    sns = SNSFalso()
    monkeypatch.setattr(lambda_function, "TOPIC_ARN", "arn:aws:sns:us-east-1:123:farmtech-alertas")
    monkeypatch.setattr(lambda_function, "_clientes", {"sns": sns, "s3": S3Falso(objetos or {})})
    return sns


def test_invocacao_direta_publica_no_sns(monkeypatch):
    sns = preparar(monkeypatch)
    resposta = lambda_function.lambda_handler(EVENTO_CRITICO, None)
    assert resposta["status"] == "enviado" and resposta["severidade"] == "CRITICO"
    enviado = sns.publicadas[0]
    corpo = json.loads(enviado["Message"])
    assert enviado["MessageStructure"] == "json" and set(corpo) == {"default", "email", "sms"}
    assert enviado["MessageAttributes"]["severidade"]["StringValue"] == "CRITICO"


def test_evento_s3_le_o_json_do_bucket(monkeypatch):
    sns = preparar(monkeypatch, {"visao/evento.json": {"origem": "visao", "deteccoes": [
        {"classe": "pessoa", "confianca": 0.92, "local": "Depósito de defensivos"}]}})
    evento = {"Records": [{"s3": {"bucket": {"name": "farmtech"}, "object": {"key": "visao/evento.json"}}}]}
    resposta = lambda_function.lambda_handler(evento, None)
    assert resposta["codigos"] == ["PESSOA_DETECTADA"]
    assert "Depósito de defensivos" in json.loads(sns.publicadas[0]["Message"])["email"]


def test_sem_alerta_nao_publica(monkeypatch):
    sns = preparar(monkeypatch)
    normal = {"origem": "sensores", "leituras": [{"umidade": 66, "ph": 6.4, "n": 1, "p": 1, "k": 1}]}
    assert lambda_function.lambda_handler(normal, None)["status"] == "sem_alertas"
    assert sns.publicadas == []


def test_api_gateway_com_body_em_texto(monkeypatch):
    preparar(monkeypatch)
    resposta = lambda_function.lambda_handler({"body": json.dumps(EVENTO_CRITICO)}, None)
    assert resposta["status"] == "enviado"
