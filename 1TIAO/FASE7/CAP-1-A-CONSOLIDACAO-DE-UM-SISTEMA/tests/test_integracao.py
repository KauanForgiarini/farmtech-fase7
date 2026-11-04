"""Testes de integração das Fases 1, 2 e 3 em uma pasta de dados temporária."""

import math

import pytest

from farmtech_core import config


@pytest.fixture()
def dados_temporarios(tmp_path, monkeypatch):
    arquivos = {chave: tmp_path / caminho.name for chave, caminho in config.ARQUIVOS.items()}
    monkeypatch.setattr(config, "ARQUIVOS", arquivos)
    for modulo in ("fase1_plantio_insumos.farmtech_fase1", "fase2_iot_irrigacao.simulador_esp32",
                   "fase3_banco_dados.banco", "fase3_banco_dados.carga_banco"):
        monkeypatch.setattr(f"{modulo}.ARQUIVOS", arquivos)
    return arquivos


def test_calculo_de_area_e_insumos():
    from fase1_plantio_insumos import farmtech_fase1 as f1

    soja = f1.montar_talhao(1, "soja", "T1", 500, 300)
    assert soja["AREA_HA"] == 15 and soja["NUM_RUAS"] == 600 and soja["METROS_LINEARES"] == 300_000
    milho = f1.montar_talhao(2, "milho", "Pivô", 100, None)
    assert math.isclose(milho["AREA_M2"], math.pi * 100 ** 2, rel_tol=1e-6)
    insumos = {i["INSUMO"]: i for i in f1.calcular_insumos(soja)}
    assert insumos["Fosfato monoamônico (MAP)"]["QUANTIDADE_TOTAL"] == 3000      # 200 kg/ha x 15 ha
    assert insumos["Fungicida para ferrugem asiática"]["QUANTIDADE_TOTAL"] == 150  # 0,5 mL/m x 300 km
    with pytest.raises(ValueError):
        f1.montar_talhao(3, "soja", "inválido", -1, 10)


def test_simulador_segue_a_regra_do_firmware():
    from fase2_iot_irrigacao.simulador_esp32 import simular
    from fase7_alertas_aws.lambda_alertas.regras_alerta import decidir_irrigacao

    for cenario in ("normal", "realista", "seca", "acidez", "saturacao"):
        for r in simular(48, cenario, 60, 1, None):
            esperado = decidir_irrigacao(r["UMIDADE_SOLO_PCT"], r["PH_SOLO"], r["CHUVA_PREVISTA_MM"],
                                         bool(r["P_PRESENTE"]), bool(r["K_PRESENTE"]))
            assert (bool(r["BOMBA_LIGADA"]), r["MOTIVO_DECISAO"]) == esperado


def test_etl_carrega_fase1_e_fase2_no_sqlite(dados_temporarios):
    from fase1_plantio_insumos import farmtech_fase1 as f1
    from fase2_iot_irrigacao.simulador_esp32 import salvar, simular
    from fase3_banco_dados.banco import Banco
    from fase3_banco_dados.carga_banco import carregar

    f1.carregar_exemplo()
    salvar(simular(24, "realista", 60, 1, None), anexar=False)
    with Banco("sqlite") as banco:
        contagens = carregar(banco)
        assert contagens["TALHAO"] == 4 and contagens["LEITURA_SENSOR"] == 24
        juncao = banco.consultar("SELECT T.NOME FROM LEITURA_SENSOR L "
                                 "JOIN TALHAO T ON T.ID_TALHAO = L.ID_TALHAO")
        assert {linha["NOME"] for linha in juncao} == {"Talhão 1 - Soja Norte"}
