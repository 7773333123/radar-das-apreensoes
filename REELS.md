# Reels e Stories do Radar — regras do dono

Valem para qualquer conversa. Arquivos de apoio em `reels/`.

## Como trabalhar
- **Primeiro o tema, depois o porquê, depois pedir permissão ("Posso fazer?").** Não gerar voz, vídeo nem arte sem o "pode".
- Economizar créditos: ser enxuto, sem gerar o site inteiro à toa.

## Reels principal do dia — ordem de relevância
1. Cocaína / pasta base (maior quantidade)
2. Maconha (maior e mais relevante)
3. Megaoperação
4. Droga em rodízio (alternar cocaína e maconha a cada dia)
5. Arma de maior porte
6. Policial preso ou outra de grande repercussão

- Só notícias novas (não repetir as do Reels anterior), com **foto real do material da MESMA apreensão**.
- Balanço/estatística de meses e decisão judicial sobre caso antigo NÃO são apreensão do dia.
- O grosso das notícias entra entre 9h e 12h: o Reels principal fica melhor perto do meio-dia.

## Extra do dia da semana
seg: Radar da Semana · ter: Fronteira · qua: Cocaína e pasta base · qui: Armas e megaoperações ·
sex: Ranking da semana · sáb: Esconderijos · dom: Semana em números. Capa do Stories no visual do dia.

## Voz e final (APROVADO — não mudar)
- Voz: ElevenLabs, Brian (`nPczCjzI2devNBz1zQrb`), `eleven_multilingual_v2`, atempo 1.1, pausa 0,5 s entre notícias.
- **Final: NUNCA gerar de novo.** Cortar a narração nova antes de "Siga" e emendar `reels/final-aprovado.mp3`
  (tempos das palavras em `reels/final-aprovado.json`). Diz: "Siga o Radar das Apreensões e acompanhe todas as
  notícias em tempo real em radar das apreensões ponto côm ponto bêérre. São centenas de apreensões por dia."
- Legenda do endereço num bloco só: "radardasapreensoes.com.br". Última cena com o endereço e @radardasapreensoes.

## Imagem e som
- Margens laterais de 90-110 px (tela cheia corta as laterais).
- Trilha preferida: percussão de trailer (`reels/trilha_trailer.py`; `reels/trilha_6noticias.py` para 6 notícias).
  Nunca música com direitos (ex.: Led Zeppelin); se o dono quiser música do Instagram, entregar sem som.
- Só vozes com licença comercial; nunca imitar voz de pessoa real.
- Humor só sobre o crime que deu errado, nunca zombando de suspeito identificável.
- Vídeos: só de fontes oficiais ou indicadas pelo dono, com crédito; nunca baixar do YouTube nem usar ferramenta
  de terceiros para baixar do Instagram; não remover marca d'água.
- Fotos de terceiros: baixar pelo workflow `reels_fotos.yml` (release "reels"); este ambiente não acessa a maioria dos sites.

## Reels diário das 9h (dono, 26/11/2026)
- Todo dia, pronto às 9h: as notícias do **dia anterior inteiro** (0h-24h, horário de Brasília), 6 a 7 notícias,
  na ordem de relevância acima, com **quantidades** conferidas, **variação** (estados, órgãos e tipos diferentes)
  e **vídeos**.
- **Vídeos oficiais primeiro** (dono: "as @ que passei são boas e mais confiáveis"): rodar antes o workflow
  `instagram_agora.yml` e usar os vídeos de `videos_instagram.json` (contas de `instagram_contas.json`), com crédito
  na tela, sem o áudio original e sem cortar marca d'água. Baixar só pela API oficial da Meta (campo media_url,
  via workflow `reels_fotos.yml`); nunca ferramenta de terceiros.
- **Sempre buscar mais informação**: ler o texto inteiro (det/, nota oficial, legenda do órgão) antes de escrever;
  conferir que a quantidade é do fato do dia (nada de origem da investigação, balanço ou caso antigo) e que a foto
  é da mesma apreensão.
- Entregar o vídeo e a legenda pronta (texto puro, 5 hashtags) para o dono **aprovar antes de postar**. Se pedir
  mudança, uma rodada de ajuste.
