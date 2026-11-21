# Radar das Apreensões — regras editoriais

Regras definidas pelo dono do site. Valem para a coleta, a geração do site e qualquer mudança de código.

- **"Apreensão" no sentido de preocupação não entra no site** (21/11/2026). Ex.: "A agenda econômica de
  Lula gera apreensão no mercado financeiro", "clima de apreensão", "investidores apreensivos". Só entra
  apreensão policial/fiscal (drogas, armas, contrabando, bens etc.). Filtro: `classificar.apreensao_sentimento`
  (usado por `classificar.relevante`); casos de teste em `python classificar.py`.
- Termos de apreensão casam só a palavra inteira: "comunica/comunicado/comunicação" não é "munição"
  (avisos de falecimento e comunicados entravam como armas, 21/11/2026).
- **Avisos fúnebres nunca entram** (funerária comunica falecimento, nota de pesar, velório, missa de
  sétimo dia), 21/11/2026: `classificar.aviso_funebre`. Ação policial ligada a isso continua entrando.
- **Versão exibida de uma notícia com várias fontes** (21/11/2026): 1) fonte primária (órgão público),
  2) matéria de licença livre com texto integral (exibida na íntegra), 3) quem publicou primeiro, 4) veículo do
  estado do fato, 5) a mais completa (`duplicatas._pontos`). A página
  lista todas as fontes com data e hora ("Fontes desta notícia"). Pequenas diferenças entre fontes (número
  arredondado, detalhe a mais) são ajuste da mesma informação: publica-se UMA notícia, nunca duas.
- **Trecho da reportagem (imprensa sem licença livre): alvo 65% do texto (faixa 60-70%)**, sempre no fim
  de uma frase (`ler_materias.trecho_de_abertura`); matéria livre/oficial: texto integral.
- **PADRÃO da página inicial: só notícias com a data do dia** (horário de Brasília), 21/11/2026: destaques,
  Fronteira, Em alta e editorias (editoria sem notícia hoje não aparece). A véspera só entra enquanto o dia
  ainda não tem nenhuma notícia (logo após a meia-noite). `assets/central.js` (`ehHoje`).
- Anos antigos (2006-2016): coleta pelo Wayback Machine (`wayback.py`, `wayback.yml`), com o link da cópia
  arquivada no archive.org; portais oficiais antigos (PF, PRF, Receita, secretarias) primeiro. 21/11/2026.
- Presos identificados só por iniciais e idade.
- Duplicatas: não tolerar. Correções à mão vão em `juiz_decisoes_revisao.json` (valem como veto do grupo);
  padrões viram regra + teste em `testes/test_duplicatas.py`.
- Notícias de Portugal/exterior, páginas que não são notícia e logotipo no lugar de foto ficam fora do site.
- Coletas: `expressa.yml` (feeds → site a cada ~8 min, faixa AGORA atualizada em seguida) e `rapido.yml`
  (complementar: Google, Bing, links, leitura, fotos), em paralelo, 21/11/2026. A faixa AGORA confere
  `agora.json` a cada 30 s.
