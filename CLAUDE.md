# Radar das Apreensões — regras editoriais

Regras definidas pelo dono do site. Valem para a coleta, a geração do site e qualquer mudança de código.

- **"Apreensão" no sentido de preocupação não entra no site** (21/11/2026). Ex.: "A agenda econômica de
  Lula gera apreensão no mercado financeiro", "clima de apreensão", "investidores apreensivos". Só entra
  apreensão policial/fiscal (drogas, armas, contrabando, bens etc.). Filtro: `classificar.apreensao_sentimento`
  (usado por `classificar.relevante`); casos de teste em `python classificar.py`.
- Presos identificados só por iniciais e idade.
- Duplicatas: não tolerar. Correções à mão vão em `juiz_decisoes_revisao.json` (valem como veto do grupo);
  padrões viram regra + teste em `testes/test_duplicatas.py`.
- Notícias de Portugal/exterior, páginas que não são notícia e logotipo no lugar de foto ficam fora do site.
