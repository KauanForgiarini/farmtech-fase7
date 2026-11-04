"""
Ir Além 1 - implantação e teste do reconhecimento de imagens com Amazon Rekognition.

Pré-requisito: o serviço de alertas da Fase 7 já implantado
(python farmtech.py aws-deploy --email ...), que cria o tópico SNS e o bucket.

Uso (na pasta do projeto):
    python IR-ALEM/src/rekognition/deploy_rekognition.py              # cria/atualiza a Lambda + gatilho
    python IR-ALEM/src/rekognition/deploy_rekognition.py --enviar data/fase6_imagens_campo/pessoa_038.jpg
    python IR-ALEM/src/rekognition/deploy_rekognition.py --comparar   # Rekognition x YOLO nas 8 imagens
    python IR-ALEM/src/rekognition/deploy_rekognition.py --remover
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.parse
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "src"))

from farmtech_core.config import ARQUIVOS, PASTA_IMAGENS_VISAO, configurar_saida  # noqa: E402
from fase7_alertas_aws import aws_config  # noqa: E402

PASTA = Path(__file__).resolve().parent
REGRAS = RAIZ / "src" / "fase7_alertas_aws" / "lambda_alertas" / "regras_alerta.py"
FUNCAO = "farmtech-rekognition"
SAIDA_COMPARACAO = RAIZ / "IR-ALEM" / "data" / "rekognition_vs_yolo.csv"


def pacote() -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(PASTA / "lambda_rekognition.py", arcname="lambda_function.py")
        zf.write(REGRAS, arcname="regras_alerta.py")
    return memoria.getvalue()


def implantar(sessao, config: dict) -> None:
    lambda_, s3 = sessao.client("lambda"), sessao.client("s3")
    ambiente = {"Variables": {"TOPIC_ARN": config["topic_arn"], "CONFIANCA_MIN": "70",
                              "LOCAL_PADRAO": "Câmera da fazenda"}}
    try:
        arn = lambda_.create_function(
            FunctionName=FUNCAO, Runtime="python3.12", Role=config["role_arn"],
            Handler="lambda_function.lambda_handler", Code={"ZipFile": pacote()},
            Timeout=60, MemorySize=256, Environment=ambiente,
            Description="FarmTech Ir Além 1 - Rekognition DetectLabels -> alertas SNS",
            Tags={"projeto": "farmtech", "fase": "7-ir-alem-1"})["FunctionArn"]
        lambda_.get_waiter("function_active_v2").wait(FunctionName=FUNCAO)
        print(f"[Lambda] {FUNCAO} criada")
    except lambda_.exceptions.ResourceConflictException:
        lambda_.update_function_code(FunctionName=FUNCAO, ZipFile=pacote())
        lambda_.get_waiter("function_updated_v2").wait(FunctionName=FUNCAO)
        lambda_.update_function_configuration(FunctionName=FUNCAO, Environment=ambiente)
        arn = lambda_.get_function(FunctionName=FUNCAO)["Configuration"]["FunctionArn"]
        print(f"[Lambda] {FUNCAO} atualizada")

    conta = arn.split(":")[4]
    try:
        lambda_.add_permission(FunctionName=FUNCAO, StatementId="s3-invoca-rekognition",
                               Action="lambda:InvokeFunction", Principal="s3.amazonaws.com",
                               SourceArn=f"arn:aws:s3:::{config['bucket']}", SourceAccount=conta)
    except lambda_.exceptions.ResourceConflictException:
        pass
    # mantém os gatilhos da Fase 7 (sensores/ e visao/) e acrescenta imagens/
    atual = s3.get_bucket_notification_configuration(Bucket=config["bucket"])
    atual.pop("ResponseMetadata", None)
    gatilhos = [g for g in atual.get("LambdaFunctionConfigurations", [])
                if not g.get("Id", "").startswith("farmtech-imagens")]
    gatilhos += [{"Id": f"farmtech-imagens-{ext}", "LambdaFunctionArn": arn,
                  "Events": ["s3:ObjectCreated:*"],
                  "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "imagens/"},
                                                     {"Name": "suffix", "Value": f".{ext}"}]}}}
                 for ext in ("jpg", "png")]
    atual["LambdaFunctionConfigurations"] = gatilhos
    s3.put_bucket_notification_configuration(Bucket=config["bucket"],
                                             NotificationConfiguration=atual)
    config["funcao_rekognition"] = FUNCAO
    aws_config.salvar(config)
    print(f"[S3] gatilho imagens/*.jpg|png -> {FUNCAO} no bucket {config['bucket']}")


def enviar(sessao, config: dict, imagem: Path, local: str) -> None:
    chave = f"imagens/{time.strftime('%Y%m%d-%H%M%S')}-{imagem.name}"
    sessao.client("s3").upload_file(str(imagem), config["bucket"], chave, ExtraArgs={
        "Metadata": {"local": urllib.parse.quote(local)}, "ContentType": "image/jpeg"})
    print(f"Imagem enviada para s3://{config['bucket']}/{chave}. A Lambda {FUNCAO} será "
          "disparada; veja o resultado no CloudWatch Logs e no e-mail.")


def comparar(sessao) -> None:
    """Rekognition (bytes locais) x YOLO da Fase 6 nas mesmas imagens das câmeras."""
    import pandas as pd

    rekognition = sessao.client("rekognition")
    yolo = pd.read_csv(ARQUIVOS["deteccoes"]) if ARQUIVOS["deteccoes"].exists() else pd.DataFrame()
    linhas = []
    for imagem in sorted(PASTA_IMAGENS_VISAO.glob("*.jpg")):
        inicio = time.perf_counter()
        resposta = rekognition.detect_labels(Image={"Bytes": imagem.read_bytes()},
                                             MaxLabels=20, MinConfidence=70)
        ms = (time.perf_counter() - inicio) * 1000
        nomes = {r["Name"]: r for r in resposta["Labels"]}
        pessoas = len(nomes.get("Person", {}).get("Instances", []))
        veiculos = sum(len(nomes.get(n, {}).get("Instances", [])) for n in ("Car", "Truck"))
        do_yolo = yolo[yolo["IMAGEM"] == imagem.name] if not yolo.empty else yolo
        linhas.append({
            "imagem": imagem.name, "classe_real": imagem.stem.split("_")[0],
            "rekognition_pessoas": pessoas, "rekognition_veiculos": veiculos,
            "yolo_pessoas": int((do_yolo["CLASSE"] == "pessoa").sum()) if not yolo.empty else None,
            "yolo_veiculos": int((do_yolo["CLASSE"] == "carro").sum()) if not yolo.empty else None,
            "latencia_rekognition_ms": round(ms), "rotulos": ", ".join(list(nomes)[:8]),
        })
        print(linhas[-1])
    pd.DataFrame(linhas).to_csv(SAIDA_COMPARACAO, index=False)
    print(f"Comparação salva em {SAIDA_COMPARACAO.relative_to(RAIZ)}")


def remover(sessao) -> None:
    try:
        sessao.client("lambda").delete_function(FunctionName=FUNCAO)
        print(f"[Lambda] {FUNCAO} removida")
    except Exception as erro:
        print(f"Nada a remover: {erro}")


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Ir Além 1 - Amazon Rekognition")
    parser.add_argument("--enviar", type=Path, help="imagem a enviar para o bucket (imagens/)")
    parser.add_argument("--local", default="Portaria principal", help="nome da câmera")
    parser.add_argument("--comparar", action="store_true", help="Rekognition x YOLO")
    parser.add_argument("--remover", action="store_true")
    args = parser.parse_args()

    config = aws_config.carregar()
    valido, detalhe = aws_config.credenciais_validas(config["regiao"])
    if not valido:
        print("Credenciais AWS inválidas ou expiradas:", detalhe)
        return 1
    if not config.get("topic_arn") and not args.comparar:
        print("Implante antes a Fase 7: python farmtech.py aws-deploy --email voce@exemplo.com")
        return 1
    sessao = aws_config.sessao(config["regiao"])
    if args.remover:
        remover(sessao)
    elif args.comparar:
        comparar(sessao)
    elif args.enviar:
        enviar(sessao, config, args.enviar, args.local)
    else:
        implantar(sessao, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
