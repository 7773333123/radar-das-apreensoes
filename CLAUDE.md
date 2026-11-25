# Radar das Apreensões — regras editoriais

Regras definidas pelo dono do site. Valem para a coleta, a geração do site e qualquer mudança de código.

- **"Apreensão" no sentido de preocupação não entra no site** (21/11/2026). Ex.: "A agenda econômica de
  Lula gera apreensão no mercado financeiro", "clima de apreensão", "investidores apreensivos". Só entra
  apreensão policial/fiscal (drogas, armas, contrabando, bens etc.). Filtro: `classificar.apreensao_sentimento`
  (usado por `classificar.relevante`); casos de teste em `python classificar.py`.
- Termos de apreensão casam só a palavra inteira: "comunica/comunicado/comunicação" não é "munição"
  (avisos de falecimento e comunicados entravam como armas, 21/11/2026).
- **Busca sem apreensão não entra** ("nenhum entorpecente foi localizado", "nada foi encontrado"), 21/11/2026:
  `classificar.sem_apreensao`.
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
  Fronteira, Em alta e editorias (editoria sem notícia hoje não aparece). Exceção (22/11/2026): a Fronteira com
  menos de 3 notícias do dia completa com as dos dias anteriores (as de hoje primeiro), para não ficar vazia. A véspera só entra enquanto o dia
  ainda não tem nenhuma notícia (logo após a meia-noite). `assets/central.js` (`ehHoje`).
- Anos antigos (2006-2016): coleta pelo Wayback Machine (`wayback.py`, `wayback.yml`), com o link da cópia
  arquivada no archive.org; portais oficiais antigos (PF, PRF, Receita, secretarias) primeiro; um servidor por
  ano em paralelo, 250 sites por ano, cursor `wayback_cursor_AAAA.json`. 21/11/2026.
- **Quantidade é só do fato noticiado** (21/11/2026): frases do resumo/texto sobre OUTRO fato ("após a apreensão
  de…", "anteriormente", "em março", "semana passada") não contam (`resumo_fatos.sem_outros_fatos`).
- **Três principais no topo** (24/11/2026, substitui a manchete única): 1ª e 2ª = maiores apreensões do dia
  COM FOTO, pelo volume de droga (kg); empate pelos critérios antigos (fonte oficial +3, instituição no título +1,
  tamanho e repercussão; desdobramentos fora). 3ª = Fronteira: PRF em Foz do Iguaçu/Santa Terezinha de Itaipu;
  senão Ponte da Amizade; senão Foz/Santa Terezinha por outro órgão; senão a ordem regional (`prioridadeFr`);
  em cada nível, o maior volume de droga. `assets/central.js` (`porVolume`, `nivelFr`).
  **REGRA DEFINITIVA dos destaques** (25/11/2026): destaque principal só com foto do material apreendido
  (`pm`, marcada por `capas_ia`), sem notícia de morte (morre, morto, óbito, executado, homicídio...) e sem
  desdobramento. Enquanto o dia não tiver 3 notícias assim, os destaques vêm das MAIORES de ontem inteiro (nunca das
  últimas da noite): depois da meia-noite a capa continua com as mais relevantes até o novo dia ter as suas
  (`assets/central.js`: `elegivel`, `MORTE`, `pool`). A Fronteira (3ª) também segue `elegivel` e prefere foto do material.
  **Cocaína sempre entre as principais** (24/11/2026): vale muito mais por quilo; se nem a 1ª nem a 2ª é de
  cocaína/pasta base/crack, a 2ª vira a maior de cocaína do dia com foto (`kgCoca`).
  Faixa abaixo delas, Fronteira e listas das editorias: maior quantidade de droga primeiro, depois repercussão
  (`porPrioridade`). Celular: só as 3 principais com foto grande; o resto com foto pequena ao lado; painel "Hoje no
  Brasil" compacto; editoria termina com o botão vermelho "Ver mais notícias" (24/11/2026).
- **Capa = foto do material apreendido** (24/11/2026): na capa vai a foto que mostra o que foi apreendido (drogas,
  armas, dinheiro, mercadorias), não a de policial, viatura ou fachada. `capas_ia.py` (Claude Haiku, todas as notícias, teto próprio US$ 8/mês,
  na coleta expressa) marca as fotos em `capas_ia.json`; `gerar_feed_site.py` põe as do material primeiro e
  `duplicatas.agrupar` troca a capa da versão exibida pela foto do material de outra fonte.
  **Sempre imagens reais** (24/11/2026): foto de arquivo (pasta de envio /AAAA/MM/ de mais de 2 meses antes da
  notícia) perde para a foto real; a versão exibida troca pela foto real de outra fonte (`foto_de_arquivo`, `_arq`).
  `capas_ia.py` confere as fotos de todas as notícias (as mais recentes primeiro).
- **Português correto** (24/11/2026), pelas referências: Bechara, Cunha & Cintra, VOLP/ABL, Manual de Redação da
  Presidência, manuais da Folha e do Estadão. Texto do Radar: zero a dez por extenso com concordância ("seis armas",
  "duas pessoas"), algarismo com unidade/valor ("6 kg", "R$ 2 mil"), idade junto do sujeito
  (`resumo_fatos.numerais_por_extenso`, `_idade_dos_presos`). Títulos das fontes: `revisar_titulos.py` (Claude Haiku,
  teto US$ 2/mês, na coleta expressa) corrige só erros claros; trava mantém números e nomes (`aceitavel`);
  registro em `revisao_titulos.json`. Roteiro dos Reels passa pela mesma revisão.
- Presos identificados só por iniciais e idade (no texto). **Foto com rosto pode** (24/11/2026): se o veículo
  original publicou a foto, ela entra como veio (no site e nos Reels); não se esconde nem desfoca rosto.
- Duplicatas: não tolerar. Correções à mão vão em `juiz_decisoes_revisao.json` (valem como veto do grupo);
  padrões viram regra + teste em `testes/test_duplicatas.py`.
- Notícias de Portugal/exterior, páginas que não são notícia e logotipo no lugar de foto ficam fora do site.
  Fato no exterior (México, EUA, Europa...) sem polícia/lugar do Brasil no título: `classificar.exterior` (22/11/2026).
- Coletas: `expressa.yml` (feeds → site a cada ~8 min, faixa AGORA atualizada em seguida) e `rapido.yml`
  (complementar: Google, Bing, links, leitura, fotos), em paralelo, 21/11/2026. A faixa AGORA confere
  `agora.json` a cada 30 s.
- **Faixa AGORA sempre em dia** (22/11/2026): notícia nova não pode ficar retida. Na fila de leitura
  (`ler_materias.py`) as das últimas 48 h passam à frente de tudo; a coleta expressa lê as das últimas 6 h na
  mesma rodada (`--recentes 6`). `verificar_site.yml` mede o atraso (meta: até ~30 min).
- **Republicação atrasada é duplicata** (22/11/2026): o mesmo fato reescrito dias depois (ex.: O Antagonista
  "Lado OA") vai ao juiz quando repete o valor do título (`duplicatas._mesmo_valor`, até 7 dias).
- **Estado mal lido não esconde duplicata** (24/11/2026): valor distintivo igual no título (R$ 850 mil, 383 tabletes)
  em até 2 dias vai ao juiz mesmo com estados diferentes; nome próprio raro em comum ("Fundeb", "Operação Impacto")
  em até 1 dia, com o mesmo material, também (`duplicatas._mesmo_valor`, `_palavra_rara`). O "mesmo" do juiz une.
- **Custo da Vercel: teto de US$ 20-30/mês** (25/11/2026). Mudança só de dados publica no máximo a cada 30 min
  (`scripts/vercel-ignorar.js`, `INTERVALO_MIN`); código/página publica na hora. Arquivo novo de dados/estado das
  coletas (ex.: `capas_ia.json`, `revisao_titulos.json`) TEM de entrar em `SO_DADOS`, senão cada rodada vira publicação
  (foi o que elevou o gasto a US$ 107 em 24-25/11). Build na máquina padrão (mais barata).
- **Site no ar nunca fica parado** (24/11/2026): no conflito de gravação entre coletas, grava-se o acervo mesclado
  junto com o site gerado (`acervo.salvar`).
- **Página inicial sem quadro vazio** (22/11/2026): "Em alta" sem matéria repercutida hoje não aparece.
- **Foto sem marca d'água nem nome de jornal** (24/11/2026): `marcas_dagua.py` aprende onde cada veículo
  carimba a marca (bordas repetidas nos mesmos pixels em fotos diferentes) e confere as fotos (`img_marca`).
  A versão exibida troca a foto carimbada pela foto limpa de outra fonte da mesma notícia
  (`duplicatas.agrupar`); sem foto limpa, fica sem foto (`sf`: o site não busca a foto original). Rotina
  `marcas_dagua.yml` (a cada 6 h); testes em `testes/test_marcas_dagua.py`. Veículo de divisa
  (campo `fronteira` em fontes.json, sem estado) não aprende estado (`localizar_uf.ufs_aprendidas`).
