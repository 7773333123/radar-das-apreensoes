
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BUSCA = '(apreensão OR apreensões OR apreende) (drogas OR armas OR contrabando OR polícia) Brasil'
url = (
    "https://news.google.com/rss/search?q="
    + urllib.parse.quote(BUSCA)
    + "&hl=pt-BR&gl=BR&ceid=BR:pt-419"
)

req = urllib.request.Request(
    url, headers={"User-Agent": "RadarDasApreensoes/1.0"}
)

with urllib.request.urlopen(req, timeout=30) as resposta:
    xml = resposta.read()

raiz = ET.fromstring(xml)
noticias = []
vistos = set()

for item in raiz.findall(".//channel/item"):
    titulo = item.findtext("title", "").strip()
    link = item.findtext("link", "").strip()
    data = item.findtext("pubDate", "").strip()
    fonte = item.findtext("source", "Google Notícias").strip()

    if not titulo or not link or link in vistos:
        continue

    vistos.add(link)
    noticias.append({
        "titulo": titulo,
        "url": link,
        "data_publicacao": data,
        "fonte": fonte
    })

resultado = {
    "atualizado_em": datetime.now(timezone.utc).isoformat(),
    "total": len(noticias),
    "noticias": noticias
}

Path("noticias.json").write_text(
    json.dumps(resultado, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(f"Coletadas {len(noticias)} notícias.")
