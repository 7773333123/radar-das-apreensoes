#!/usr/bin/env python3
"""Baixa os brasões oficiais das instituições (Wikidata/Wikimedia Commons) para img/brasoes/.

Usados no lugar da foto quando a matéria não tem imagem (assets/core.js). Para cada
instituição procura o item no Wikidata e usa a imagem de brasão (P94), selo (P158) ou
logotipo (P154); a imagem é baixada já em PNG de 256 px pelo Commons. Gera:
- img/brasoes/<chave>.png
- img/brasoes/origem.json: arquivo do Commons, item do Wikidata e página de cada imagem (crédito)
- assets/brasoes.js: lista das chaves disponíveis (o site só usa o brasão que existe)

Roda no GitHub Actions (brasoes.yml); as imagens são conferidas à mão antes de publicar.
Correções manuais (arquivo certo do Commons) em MANUAL.
"""
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent
PASTA = RAIZ / 'img' / 'brasoes'
UA = 'RadarDasApreensoes/1.0 (brasoes; https://www.radardasapreensoes.com.br)'
ESTADOS = {
    'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal',
    'ES': 'Espírito Santo', 'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul',
    'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí',
    'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima',
    'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins',
}
# chave -> (buscas no Wikidata, palavras que o rótulo precisa ter)
ALVOS = {
    'prf': (['Polícia Rodoviária Federal'], ['rodoviaria', 'federal']),
    'pf': (['Polícia Federal do Brasil', 'Polícia Federal'], ['policia', 'federal']),
    'receita': (['Receita Federal do Brasil', 'Secretaria Especial da Receita Federal do Brasil'], ['receita', 'federal']),
    'forca-nacional': (['Força Nacional de Segurança Pública'], ['forca', 'nacional']),
    'marinha': (['Marinha do Brasil'], ['marinha']),
    'exercito': (['Exército Brasileiro'], ['exercito']),
    'ibama': (['Instituto Brasileiro do Meio Ambiente e dos Recursos Naturais Renováveis', 'Ibama'], ['ibama', 'meio ambiente']),
    'dof': (['Departamento de Operações de Fronteira'], ['fronteira']),
    'gefron': (['Grupo Especial de Segurança de Fronteira'], ['fronteira']),
    'bpfron': (['Batalhão de Polícia de Fronteira'], ['fronteira']),
}
for uf, nome in ESTADOS.items():
    de = 'do' if uf in ('AC', 'AP', 'AM', 'CE', 'DF', 'ES', 'MA', 'PA', 'PR', 'PI', 'RJ', 'RN', 'RS', 'TO') else (
        'da' if uf in ('BA', 'PB') else 'de')
    ALVOS[f'pm-{uf.lower()}'] = ([f'Polícia Militar {de} {nome}', f'Polícia Militar do Estado {de} {nome}',
                                  f'Polícia Militar do Estado de {nome}', f'Polícia Militar {nome}'], ['militar'])
    ALVOS[f'pc-{uf.lower()}'] = ([f'Polícia Civil {de} {nome}', f'Polícia Civil do Estado {de} {nome}',
                                  f'Polícia Civil do Estado de {nome}', f'Polícia Civil {nome}'], ['civil'])
# Arquivos do Commons escolhidos à mão (quando a busca acha o item errado ou sem imagem).
MANUAL = {}
# Conferidos à mão e recusados (imagem de outra unidade ou ilegível): ficam com o nome do órgão.
RECUSADOS = {'bpfron', 'pc-mt', 'pc-ma'}


def normal(t):
    t = unicodedata.normalize('NFKD', t or '')
    return re.sub(r'[^a-z0-9 ]+', ' ', ''.join(c for c in t if not unicodedata.combining(c)).lower())


def get_json(url):
    for tentativa in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': UA}), timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception:
            time.sleep(2 * (tentativa + 1))
    return {}


def item_wikidata(buscas, palavras, uf=None):
    estado = normal(ESTADOS[uf]) if uf else ''
    for busca in buscas:
        r = get_json('https://www.wikidata.org/w/api.php?' + urlencode(
            {'action': 'wbsearchentities', 'search': busca, 'language': 'pt', 'uselang': 'pt', 'limit': 8, 'format': 'json'}))
        for c in r.get('search', []):
            rotulo = normal(c.get('label', '') + ' ' + c.get('description', ''))
            # O nome do estado no FIM do rótulo (evita Mato Grosso x Mato Grosso do Sul, Pará x Paraná).
            fim = re.sub(r'\s+', ' ', normal(c.get('label', ''))).strip()
            if all(p in rotulo for p in palavras) and (not estado or fim.endswith(re.sub(r'\s+', ' ', estado).strip())):
                return c['id'], c.get('label', '')
    return None, None


def imagem_do_item(qid):
    r = get_json('https://www.wikidata.org/w/api.php?' + urlencode(
        {'action': 'wbgetentities', 'ids': qid, 'props': 'claims', 'format': 'json'}))
    claims = r.get('entities', {}).get(qid, {}).get('claims', {})
    for prop in ('P94', 'P158', 'P154'):  # brasão, selo, logotipo
        for c in claims.get(prop, []):
            v = c.get('mainsnak', {}).get('datavalue', {}).get('value')
            if isinstance(v, str) and v:
                return v, prop
    return None, None


def baixar_arquivo(arquivo, destino):
    r = get_json('https://commons.wikimedia.org/w/api.php?' + urlencode(
        {'action': 'query', 'titles': f'File:{arquivo}', 'prop': 'imageinfo', 'iiprop': 'url|extmetadata',
         'iiurlwidth': 256, 'format': 'json'}))
    paginas = r.get('query', {}).get('pages', {})
    info = next(iter(paginas.values()), {}).get('imageinfo', [{}])[0]
    url = info.get('thumburl') or info.get('url')
    if not url:
        return None
    with urlopen(Request(url, headers={'User-Agent': UA}), timeout=60) as resp:
        destino.write_bytes(resp.read())
    meta = info.get('extmetadata', {})
    return {'pagina': info.get('descriptionurl', ''), 'licenca': (meta.get('LicenseShortName') or {}).get('value', '')}


def main():
    PASTA.mkdir(parents=True, exist_ok=True)
    origem = {}
    for chave, (buscas, palavras) in ALVOS.items():
        if chave in RECUSADOS:
            continue
        uf = chave.split('-')[1].upper() if chave[:3] in ('pm-', 'pc-') else None
        if chave in MANUAL:
            arquivo, qid, rotulo, prop = MANUAL[chave], '', 'manual', 'manual'
        else:
            qid, rotulo = item_wikidata(buscas, palavras, uf)
            arquivo, prop = imagem_do_item(qid) if qid else (None, None)
        if not arquivo:
            print(f'{chave:16} sem imagem (item: {qid} {rotulo})')
            continue
        destino = PASTA / f'{chave}.png'
        try:
            info = baixar_arquivo(arquivo, destino)
        except Exception as exc:
            info = None
            print(f'{chave:16} erro ao baixar {arquivo}: {exc}')
        if info:
            origem[chave] = {'arquivo': arquivo, 'item': qid, 'rotulo': rotulo, 'propriedade': prop, **info}
            print(f'{chave:16} {qid} {rotulo} -> {arquivo} ({prop}, {info["licenca"]})')
        time.sleep(0.5)
    (PASTA / 'origem.json').write_text(json.dumps(origem, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    chaves = sorted(origem)
    (RAIZ / 'assets' / 'brasoes.js').write_text(
        '// Gerado por baixar_brasoes.py: brasões oficiais disponíveis em /img/brasoes/<chave>.png.\n'
        f'export const BRASOES = new Set({json.dumps(chaves)});\n', encoding='utf-8')
    print(f'{len(chaves)} de {len(ALVOS)} brasões baixados.')


if __name__ == '__main__':
    main()
