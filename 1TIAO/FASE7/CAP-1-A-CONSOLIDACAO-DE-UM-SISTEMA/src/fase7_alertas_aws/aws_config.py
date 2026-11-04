"""
Configuração dos recursos AWS do serviço de alertas.

O deploy_aws.py grava data/aws_config.json (sem segredos: apenas nomes e ARNs).
As credenciais nunca ficam no projeto: o boto3 as lê do ~/.aws/credentials
(bloco "AWS CLI" do AWS Academy Learner Lab) ou de variáveis de ambiente.
"""

from __future__ import annotations

import json
import os

from farmtech_core.config import ARQUIVOS

PADRAO = {
    "regiao": "us-east-1",           # o Learner Lab só libera us-east-1 e us-west-2
    "topico_sns": "farmtech-alertas",
    "funcao_lambda": "farmtech-alertas",
    "topic_arn": "",
    "bucket": "",
}


def carregar() -> dict:
    config = dict(PADRAO)
    if ARQUIVOS["aws_config"].exists():
        config.update(json.loads(ARQUIVOS["aws_config"].read_text(encoding="utf-8")))
    # variáveis de ambiente têm prioridade (úteis em CI ou em outra conta)
    config["regiao"] = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", config["regiao"]))
    config["topic_arn"] = os.getenv("FARMTECH_SNS_TOPIC_ARN", config["topic_arn"])
    config["bucket"] = os.getenv("FARMTECH_S3_BUCKET", config["bucket"])
    config["funcao_lambda"] = os.getenv("FARMTECH_LAMBDA", config["funcao_lambda"])
    return config


def salvar(config: dict) -> None:
    ARQUIVOS["aws_config"].parent.mkdir(parents=True, exist_ok=True)
    ARQUIVOS["aws_config"].write_text(json.dumps(config, indent=2, ensure_ascii=False),
                                      encoding="utf-8")


def sessao(regiao: str | None = None):
    import boto3

    return boto3.session.Session(region_name=regiao or carregar()["regiao"])


def credenciais_validas(regiao: str | None = None) -> tuple[bool, str]:
    """Confere as credenciais com o STS (as do Learner Lab expiram a cada sessão)."""
    try:
        identidade = sessao(regiao).client("sts").get_caller_identity()
        return True, identidade["Arn"]
    except Exception as erro:  # sem credenciais, expiradas ou sem rede
        return False, f"{type(erro).__name__}: {erro}"
