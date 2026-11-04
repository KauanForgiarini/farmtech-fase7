"""
FarmTech Solutions - Fase 7: implantação do serviço de alertas na AWS.

Cria (ou atualiza) na conta do AWS Academy Learner Lab, região us-east-1:

  1. Tópico Amazon SNS "farmtech-alertas" + assinatura de e-mail (e SMS opcional,
     filtrado para alertas ALTO/CRITICO);
  2. Bucket Amazon S3 privado e criptografado que recebe os eventos JSON dos
     sensores (prefixo sensores/) e da visão computacional (prefixo visao/);
  3. Função AWS Lambda "farmtech-alertas" (Python 3.12, role LabRole) com as
     regras de alerta; o S3 dispara a função a cada novo arquivo.

O Learner Lab não permite criar roles IAM: a função usa a LabRole existente.
Os nomes e ARNs criados ficam em data/aws_config.json (sem credenciais).

Uso:
    python src/fase7_alertas_aws/deploy_aws.py --email funcionario@fazenda.com
    python src/fase7_alertas_aws/deploy_aws.py --email a@x.com --telefone +5555999999999
    python src/fase7_alertas_aws/deploy_aws.py --testar     # invoca a Lambda com um evento crítico
    python src/fase7_alertas_aws/deploy_aws.py --remover    # apaga tudo (economiza créditos)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmtech_core.config import configurar_saida
from fase7_alertas_aws import aws_config

PASTA_LAMBDA = Path(__file__).resolve().parent / "lambda_alertas"
RUNTIME = "python3.12"


def empacotar_lambda() -> bytes:
    """Zip com lambda_function.py e regras_alerta.py na raiz (formato exigido pela Lambda)."""
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
        for arquivo in ("lambda_function.py", "regras_alerta.py"):
            zf.write(PASTA_LAMBDA / arquivo, arcname=arquivo)
    return memoria.getvalue()


def criar_topico(sns, nome: str, emails: list[str], telefone: str | None,
                 kms: bool) -> str:
    arn = sns.create_topic(Name=nome, Attributes={"DisplayName": "FarmTech"})["TopicArn"]
    if kms:
        sns.set_topic_attributes(TopicArn=arn, AttributeName="KmsMasterKeyId",
                                 AttributeValue="alias/aws/sns")
    existentes = {s["Endpoint"] for s in
                  sns.list_subscriptions_by_topic(TopicArn=arn).get("Subscriptions", [])}
    for email in emails:
        if email not in existentes:
            sns.subscribe(TopicArn=arn, Protocol="email", Endpoint=email)
            print(f"  [SNS] assinatura de e-mail criada para {email}: confirme no link recebido.")
    if telefone and telefone not in existentes:
        sns.subscribe(TopicArn=arn, Protocol="sms", Endpoint=telefone,
                      Attributes={"FilterPolicy": json.dumps(
                          {"severidade": ["CRITICO", "ALTO"]})})
        print(f"  [SNS] assinatura SMS criada para {telefone} (somente ALTO/CRITICO).")
    print(f"  [SNS] tópico: {arn}")
    return arn


def criar_bucket(s3, nome: str, regiao: str) -> None:
    try:
        if regiao == "us-east-1":
            s3.create_bucket(Bucket=nome)
        else:
            s3.create_bucket(Bucket=nome,
                             CreateBucketConfiguration={"LocationConstraint": regiao})
        print(f"  [S3] bucket criado: {nome}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"  [S3] bucket já existe: {nome}")
    s3.put_public_access_block(Bucket=nome, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True,
        "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=nome, ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    s3.put_bucket_policy(Bucket=nome, Policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Sid": "SomenteHTTPS", "Effect": "Deny", "Principal": "*",
                       "Action": "s3:*",
                       "Resource": [f"arn:aws:s3:::{nome}", f"arn:aws:s3:::{nome}/*"],
                       "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}))


def criar_lambda(lambda_, nome: str, role_arn: str, topic_arn: str) -> str:
    ambiente = {"Variables": {"TOPIC_ARN": topic_arn, "SEVERIDADE_MINIMA": "MEDIO",
                              "NOME_FAZENDA": "Fazenda FarmTech"}}
    codigo = empacotar_lambda()
    try:
        arn = lambda_.create_function(
            FunctionName=nome, Runtime=RUNTIME, Role=role_arn,
            Handler="lambda_function.lambda_handler", Code={"ZipFile": codigo},
            Timeout=30, MemorySize=128, Environment=ambiente,
            Description="FarmTech Fase 7 - regras de alerta de sensores e visão -> SNS",
            Tags={"projeto": "farmtech", "fase": "7"})["FunctionArn"]
        print(f"  [Lambda] função criada: {nome}")
        lambda_.get_waiter("function_active_v2").wait(FunctionName=nome)
    except lambda_.exceptions.ResourceConflictException:
        lambda_.update_function_code(FunctionName=nome, ZipFile=codigo)
        lambda_.get_waiter("function_updated_v2").wait(FunctionName=nome)
        lambda_.update_function_configuration(FunctionName=nome, Environment=ambiente,
                                              Timeout=30, MemorySize=128)
        lambda_.get_waiter("function_updated_v2").wait(FunctionName=nome)
        arn = lambda_.get_function(FunctionName=nome)["Configuration"]["FunctionArn"]
        print(f"  [Lambda] função atualizada: {nome}")
    return arn


def ligar_gatilho_s3(s3, lambda_, bucket: str, funcao_arn: str, conta: str) -> None:
    try:
        lambda_.add_permission(FunctionName=funcao_arn, StatementId="s3-invoca-farmtech",
                               Action="lambda:InvokeFunction", Principal="s3.amazonaws.com",
                               SourceArn=f"arn:aws:s3:::{bucket}", SourceAccount=conta)
    except lambda_.exceptions.ResourceConflictException:
        pass  # permissão já concedida em um deploy anterior
    # preserva outros gatilhos do bucket (ex.: imagens/ do Ir Além 1 - Rekognition)
    atual = s3.get_bucket_notification_configuration(Bucket=bucket)
    atual.pop("ResponseMetadata", None)
    gatilhos = [g for g in atual.get("LambdaFunctionConfigurations", [])
                if g.get("Id") not in {"farmtech-sensores", "farmtech-visao"}]
    gatilhos += [
        {"Id": f"farmtech-{prefixo}", "LambdaFunctionArn": funcao_arn,
         "Events": ["s3:ObjectCreated:*"],
         "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": f"{prefixo}/"},
                                            {"Name": "suffix", "Value": ".json"}]}}}
        for prefixo in ("sensores", "visao")]
    atual["LambdaFunctionConfigurations"] = gatilhos
    s3.put_bucket_notification_configuration(Bucket=bucket, NotificationConfiguration=atual)
    print("  [S3] gatilho configurado: sensores/*.json e visao/*.json -> Lambda")


def testar(sessao, config: dict) -> None:
    evento = {"origem": "sensores", "leituras": [{
        "data_hora": time.strftime("%Y-%m-%d %H:%M:%S"), "talhao": "Talhão 1 - Soja Norte",
        "umidade": 34.0, "ph": 4.8, "temperatura": 36.0, "chuva_mm": 0.0,
        "n": 1, "p": 0, "k": 0, "bomba": 0, "motivo": "ph_fora_faixa"}]}
    resposta = sessao.client("lambda").invoke(FunctionName=config["funcao_lambda"],
                                              Payload=json.dumps(evento).encode())
    print("Resposta da Lambda:", resposta["Payload"].read().decode())


def remover(sessao, config: dict) -> None:
    lambda_, s3, sns = (sessao.client(s) for s in ("lambda", "s3", "sns"))
    try:
        lambda_.delete_function(FunctionName=config["funcao_lambda"])
        print("  [Lambda] função removida")
    except lambda_.exceptions.ResourceNotFoundException:
        pass
    if config.get("bucket"):
        try:
            objetos = s3.list_objects_v2(Bucket=config["bucket"]).get("Contents", [])
            if objetos:
                s3.delete_objects(Bucket=config["bucket"], Delete={
                    "Objects": [{"Key": o["Key"]} for o in objetos]})
            s3.delete_bucket(Bucket=config["bucket"])
            print("  [S3] bucket removido")
        except s3.exceptions.NoSuchBucket:
            pass
    if config.get("topic_arn"):
        sns.delete_topic(TopicArn=config["topic_arn"])
        print("  [SNS] tópico removido")


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Implanta o serviço de alertas na AWS")
    parser.add_argument("--email", action="append", default=[],
                        help="e-mail de funcionário (pode repetir)")
    parser.add_argument("--telefone", help="celular para SMS no formato E.164 (+55...)")
    parser.add_argument("--regiao", default=None, help="padrão: us-east-1")
    parser.add_argument("--role-arn", help="padrão: arn:aws:iam::<conta>:role/LabRole")
    parser.add_argument("--sns-kms", action="store_true",
                        help="criptografa o tópico com a chave gerenciada aws/sns")
    parser.add_argument("--testar", action="store_true", help="invoca a Lambda com evento crítico")
    parser.add_argument("--remover", action="store_true", help="remove os recursos criados")
    args = parser.parse_args()

    config = aws_config.carregar()
    if args.regiao:
        config["regiao"] = args.regiao
    valido, identidade = aws_config.credenciais_validas(config["regiao"])
    if not valido:
        print("Credenciais AWS inválidas ou expiradas:", identidade)
        print("No Learner Lab: Start Lab > AWS Details > AWS CLI > Show, e cole o bloco em "
              "~/.aws/credentials (perfil [default]).")
        return 1
    sessao = aws_config.sessao(config["regiao"])
    print(f"Conta AWS: {identidade} | região {config['regiao']}")

    if args.remover:
        remover(sessao, config)
        return 0
    if args.testar:
        testar(sessao, config)
        return 0
    if not args.email and not config.get("topic_arn"):
        parser.error("informe ao menos um --email para receber os alertas")

    conta = sessao.client("sts").get_caller_identity()["Account"]
    role_arn = args.role_arn or f"arn:aws:iam::{conta}:role/LabRole"
    config["bucket"] = config.get("bucket") or f"farmtech-alertas-{conta}-{config['regiao']}"

    print("1/4 Amazon SNS")
    config["topic_arn"] = criar_topico(sessao.client("sns"), config["topico_sns"],
                                       args.email, args.telefone, args.sns_kms)
    print("2/4 Amazon S3")
    criar_bucket(sessao.client("s3"), config["bucket"], config["regiao"])
    print("3/4 AWS Lambda")
    config["funcao_arn"] = criar_lambda(sessao.client("lambda"), config["funcao_lambda"],
                                        role_arn, config["topic_arn"])
    print("4/4 Gatilho S3 -> Lambda")
    ligar_gatilho_s3(sessao.client("s3"), sessao.client("lambda"), config["bucket"],
                     config["funcao_arn"], conta)

    config["role_arn"] = role_arn
    config["implantado_em"] = time.strftime("%Y-%m-%d %H:%M:%S")
    aws_config.salvar(config)
    console = f"https://{config['regiao']}.console.aws.amazon.com"
    print("\nImplantação concluída. Configuração salva em data/aws_config.json")
    print(f"  SNS:    {console}/sns/v3/home?region={config['regiao']}#/topics")
    print(f"  Lambda: {console}/lambda/home?region={config['regiao']}#/functions/"
          f"{config['funcao_lambda']}")
    print(f"  S3:     https://s3.console.aws.amazon.com/s3/buckets/{config['bucket']}")
    print("Próximo passo: confirme a assinatura no e-mail e rode "
          "'python farmtech.py alertas --modo s3'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
