# Fontes e licenças do dataset

## Origem

As 80 imagens utilizadas nesta fase foram selecionadas do **Open Images Dataset V7**, nas classes **Person** e **Car**, e organizadas localmente para treino, validação e teste.

Página oficial do dataset:
https://storage.googleapis.com/openimages/web/index.html

Página oficial de download/metadados:
https://storage.googleapis.com/openimages/web/download_v7.html

## Licenças

De acordo com a documentação oficial do Open Images V7:

- as **anotações** são disponibilizadas por Google LLC sob **CC BY 4.0**;
- as **imagens** são listadas como possuindo licença **CC BY 2.0**;
- os metadados oficiais incluem, para cada imagem, o Open Images ID, URL original, página original, licença, autor e título;
- a própria documentação recomenda verificar o status de licença de cada imagem individualmente.

O arquivo `fontes_openimages.csv`, gerado durante a preparação do dataset, registra o nome do arquivo, classe, split e o **Open Images image_id** de cada fotografia selecionada. Esse ID permite relacionar cada item aos metadados oficiais de origem.

## Observação acadêmica

O dataset foi usado exclusivamente para fins acadêmicos neste protótipo da FIAP. As imagens não são redistribuídas diretamente neste repositório; o compartilhamento do conjunto utilizado é feito por link do Google Drive para avaliação.

## Arquivos de registro

`fontes.csv` neste repositório é apenas um modelo vazio para coleta manual. Não contém a origem das 80 imagens utilizadas. O script gera o registro `FarmTech_Fase6/fontes_openimages.csv`, que deve acompanhar o dataset no Drive. A presença e o preenchimento desse arquivo no Drive, incluindo a conferência das licenças individuais, não foram verificados nesta revisão.
