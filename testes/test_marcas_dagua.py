#!/usr/bin/env python3
"""Testes da detecção de marca d'água (marcas_dagua.py): fotos sintéticas com cenas diferentes,
com e sem o nome do jornal carimbado no mesmo canto."""
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import marcas_dagua as md  # noqa: E402


def cena(semente, marca=False, tam=(800, 500)):
    r = random.Random(semente)
    img = Image.new('RGB', tam, tuple(r.randrange(60, 200) for _ in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(r.randrange(6, 14)):  # objetos da cena em lugares diferentes
        x, y = r.randrange(tam[0]), r.randrange(tam[1])
        w, h = r.randrange(40, 300), r.randrange(40, 250)
        forma = d.rectangle if r.random() < 0.5 else d.ellipse
        forma([x, y, x + w, y + h], fill=tuple(r.randrange(256) for _ in range(3)))
    img = img.filter(ImageFilter.GaussianBlur(2))
    if marca:  # nome do jornal no canto inferior direito, sempre no mesmo lugar
        d = ImageDraw.Draw(img)
        d.rectangle([560, 420, 780, 480], outline=(255, 255, 255), width=6)
        for k in range(6):
            d.rectangle([575 + k * 34, 435, 595 + k * 34, 465], fill=(255, 255, 255))
    b = io.BytesIO()
    img.save(b, 'JPEG', quality=85)
    return b.getvalue()


falhas = 0


def confere(nome, cond):
    global falhas
    print(('ok   ' if cond else 'FALHA') + ' ' + nome)
    falhas += 0 if cond else 1


com = [md.bordas(cena(s, True)) for s in range(12)]
sem = [md.bordas(cena(100 + s)) for s in range(12)]
m_com = md.mascara(com)
m_sem = md.mascara(sem)
confere('veículo que carimba o nome no canto: máscara encontrada', m_com != 0)
confere('veículo sem marca: nenhuma máscara', m_sem == 0)
pix = [k for k in range(md.LADO * md.LADO) if m_com >> k & 1]
confere('máscara fica no canto inferior direito', all(k % md.LADO >= 40 and k // md.LADO >= 48 for k in pix))
novas_com = [md.nota(md.bordas(cena(500 + s, True)), m_com) for s in range(6)]
novas_sem = [md.nota(md.bordas(cena(600 + s)), m_com) for s in range(6)]
confere(f'foto nova carimbada reconhecida {[round(x, 2) for x in novas_com]}', all(x >= md.MARCADA for x in novas_com))
confere(f'foto nova limpa do mesmo veículo passa {[round(x, 2) for x in novas_sem]}', all(x < md.MARCADA for x in novas_sem))
outro_tam = md.nota(md.bordas(cena(700, True)), m_com)
confere('poucas fotos: não aprende', md.mascara(com[:5]) == 0)

# Linha reta (tarja de foto vertical) não é marca.
def tarja(s):
    img = Image.open(io.BytesIO(cena(800 + s)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 120, 500], fill=(0, 0, 0))
    d.rectangle([680, 0, 800, 500], fill=(0, 0, 0))
    b = io.BytesIO(); img.save(b, 'JPEG'); return b.getvalue()
confere('tarjas pretas laterais não viram marca', md.mascara([md.bordas(tarja(s)) for s in range(12)]) == 0)

# foto_com_marca: conferida vale; sem conferir, vale o veículo que carimba quase tudo.
masc = {'site.com.br': {'m': 'ff', 'pct': 0.9}, 'limpo.com.br': {'m': '', 'pct': 0}, 'as-vezes.com.br': {'m': 'ff', 'pct': 0.3}}
n = {'url': 'https://www.site.com.br/x', 'img_marca': {'https://a/1.jpg': 0}}
confere('foto conferida limpa passa', not md.foto_com_marca(n, 'https://a/1.jpg', masc))
confere('foto não conferida de veículo que carimba 90%: fora', md.foto_com_marca(n, 'https://a/2.jpg', masc))
confere('veículo sem marca: passa', not md.foto_com_marca({'url': 'https://limpo.com.br/x'}, 'https://a/3.jpg', masc))
confere('veículo que carimba às vezes: só a conferida sai',
        not md.foto_com_marca({'url': 'https://as-vezes.com.br/x'}, 'https://a/4.jpg', masc)
        and md.foto_com_marca({'url': 'https://as-vezes.com.br/x', 'img_marca': {'https://a/4.jpg': 1}}, 'https://a/4.jpg', masc))
# Cantos (24/11/2026): fotos de formatos diferentes (retrato/paisagem) com a marca a distância fixa do canto.
def canto(semente, marca, tam):
    r = random.Random(semente)
    w, h = tam
    img = Image.new('RGB', tam, (120, 120, 120))
    d = ImageDraw.Draw(img)
    for _ in range(12):
        x, y = r.randrange(w), r.randrange(h)
        d.ellipse([x, y, x + r.randrange(30, 200), y + r.randrange(30, 200)], fill=tuple(r.randrange(256) for _ in range(3)))
    if marca:
        e = w / 256
        d.rectangle([w - 60 * e, h - 35 * e, w - 10 * e, h - 12 * e], outline=(255, 255, 255), width=max(2, int(2 * e)))
    b = io.BytesIO(); img.save(b, 'JPEG'); return b.getvalue()
TAMS = [(800, 500), (400, 600), (1000, 560), (500, 500)]
ass = [md.assinatura(canto(k, True, TAMS[k % 4])) for k in range(12)]
zona = md.mascara([z['inf_dir'] for _, z in ass], md.ZW, md.ZH)
confere('formatos variados: o canto inferior direito acha a marca',
        zona != 0)
info = {'z': {'inf_dir': format(zona, 'x')}}
confere('foto nova carimbada (outro formato) reconhecida pelo canto',
        md.nota_total(md.assinatura(canto(90, True, (640, 900))), info) >= md.MARCADA)
confere('foto nova limpa passa pelo canto', md.nota_total(md.assinatura(canto(91, False, (640, 900))), info) < md.MARCADA)
sem = [md.assinatura(canto(200 + k, False, TAMS[k % 4])) for k in range(12)]
confere('veículo sem marca: nenhum canto aprende', all(md.mascara([z[c] for _, z in sem], md.ZW, md.ZH) == 0 for c in md.ZONAS))
# Marcado à mão (fontes.json "marca_dagua": true): toda foto conta como carimbada.
confere('veículo marcado à mão: foto conferida limpa também sai',
        md.foto_com_marca({'url': 'https://manual.com.br/x', 'img_marca': {'u': 0}}, 'u', {'manual.com.br': {'manual': 1}}))
print('falhas:', falhas)
sys.exit(1 if falhas else 0)
