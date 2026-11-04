# Dashboard final (evolução da dashboard da Fase 4)

`app.py` (Streamlit, `st.navigation`) com uma página por fase em `paginas/`. Cada botão chama
`farmtech_core.servicos.executar()`, que roda o mesmo programa do comando `python farmtech.py <serviço>`,
mostra a saída e atualiza o banco da Fase 3.

```bash
python farmtech.py dashboard      # ou: streamlit run src/dashboard/app.py
```
