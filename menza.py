"""Stáhne jídelníček menzy UTB (výdejna U4), nechá AI ohodnotit vhodnost jídel
pro člověka, který musí úplně vyloučit laktózu, a vygeneruje docs/index.html."""

import html
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from zoneinfo import ZoneInfo

RSS_URL = "https://jidelnicek.utb.cz/webkredit/Api/Ordering/Rss?canteenId=2"  # 2 = Výdejna U4
SEKCE = {"Polévka", "Oběd", "Minutka", "Pizza"}  # "Steril. jídla" a "Obaly" vynecháváme
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
PRAHA = ZoneInfo("Europe/Prague")

PROMPT = """Jsi nutriční poradce. Hodnotíš jídla ze školní menzy pro člověka,
který musí ÚPLNĚ vyloučit laktózu a mléčné výrobky (mléko, smetana, máslo, sýr,
jogurt, tvaroh, syrovátka, mléčná čokoláda apod.).

Máš jen názvy jídel, ne recepty. Vycházej z typické české receptury.
U každého jídla urči semafor:
- "zelena"   = podle názvu i běžné receptury mléčné výrobky neobsahuje
- "oranzova" = může obsahovat skryté mléko (kaše, omáčky, obalování, zahuštění, pečivo) – ověřit v kuchyni
- "cervena"  = mléčné výrobky obsahuje zjevně (smetana, sýr, máslo, jogurt v názvu nebo typicky v receptu)

Vrať JSON pole objektů {"id": <číslo>, "semafor": "...", "duvod": "<krátce, max 12 slov, česky>"}
pro každé jídlo ze vstupu, nic jiného.

Jídla:
"""


def stahni_jidelnicek():
    """Vrátí seznam dnů: [{"datum": date, "nazev": "pondělí 5. října 2026", "jidla": [{"sekce", "nazev"}]}]."""
    with urllib.request.urlopen(RSS_URL, timeout=30) as r:
        xml = r.read().decode("utf-8")
    # Feed tvrdí encoding="utf-16", ale ve skutečnosti je v UTF-8 – hlavičku zahodíme.
    root = ET.fromstring(re.sub(r"^<\?xml[^>]*\?>", "", xml.lstrip("﻿")))
    dny = []
    for item in root.iter("item"):
        datum = date.fromisoformat(item.find("{http://www.w3.org/2005/Atom}updated").text[:10])
        popis = item.find("description").text or ""
        jidla = []
        for sekce, seznam in re.findall(r"<h2>(.*?)</h2>\s*<ul>(.*?)</ul>", popis, re.S):
            if sekce.strip() not in SEKCE:
                continue
            for li in re.findall(r"<li>(.*?)</li>", seznam, re.S):
                nazev = re.sub(r"^\d+\s*g\s+", "", html.unescape(li).strip())  # "120g Guláš" -> "Guláš"
                if nazev and "Salát velký" not in nazev:
                    jidla.append({"sekce": sekce.strip(), "nazev": nazev})
        if jidla:
            dny.append({"datum": datum, "nazev": item.find("title").text, "jidla": jidla})
    return dny


def ohodnot(jidla):
    """Pošle všechna jídla najednou do Gemini a doplní do nich "semafor" a "duvod"."""
    seznam = "\n".join(f'{i}: {j["nazev"]}' for i, j in enumerate(jidla))
    telo = {
        "contents": [{"parts": [{"text": PROMPT + seznam}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps(telo).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        odpoved = json.load(r)
    hodnoceni = json.loads(odpoved["candidates"][0]["content"]["parts"][0]["text"])
    for h in hodnoceni:
        jidla[int(h["id"])].update(semafor=h["semafor"], duvod=h["duvod"])


def vyrob_html(dny, aktualizace):
    ikony = {"zelena": "🟢", "oranzova": "🟡", "cervena": "🔴"}
    bloky = []
    for den in dny:
        radky = "".join(
            f'<li class="{j.get("semafor", "")}"><span class="ikona">{ikony.get(j.get("semafor"), "⚪")}</span>'
            f'<div><strong>{html.escape(j["nazev"])}</strong><small>{html.escape(j["sekce"])} · '
            f'{html.escape(j.get("duvod", "nehodnoceno"))}</small></div></li>'
            for j in sorted(den["jidla"], key=lambda j: list(ikony).index(j["semafor"]) if j.get("semafor") in ikony else 3)
        )
        bloky.append(f'<section><h2>{html.escape(den["nazev"].capitalize())}</h2><ul>{radky}</ul></section>')
    obsah = "".join(bloky) or "<p>Menza na tento týden zatím nezveřejnila jídelníček.</p>"
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Menza bez laktózy</title>
<style>
:root {{ --bg:#f6f5f2; --karta:#fff; --text:#1d1d1f; --slaby:#6b6b70; --okraj:#e4e2dc; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141416; --karta:#1e1e21; --text:#f2f2f4; --slaby:#9a9aa2; --okraj:#2e2e33; }} }}
body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.45 system-ui,-apple-system,sans-serif; }}
main {{ max-width:720px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ margin:0 0 4px; font-size:1.7rem; }}
.meta, small {{ color:var(--slaby); }}
.legenda {{ display:flex; flex-wrap:wrap; gap:8px 18px; margin:16px 0 8px; font-size:.9rem; }}
.upozorneni {{ font-size:.85rem; color:var(--slaby); border-left:3px solid var(--okraj); padding-left:10px; }}
section {{ background:var(--karta); border:1px solid var(--okraj); border-radius:12px; padding:4px 16px; margin-top:16px; }}
h2 {{ font-size:1.1rem; margin:14px 0 6px; }}
ul {{ list-style:none; margin:0; padding:0; }}
li {{ display:flex; gap:10px; padding:10px 0; border-top:1px solid var(--okraj); }}
li:first-child {{ border-top:0; }}
li small {{ display:block; font-size:.85rem; }}
li.cervena strong {{ font-weight:500; color:var(--slaby); }}
.ikona {{ flex:none; }}
</style></head><body><main>
<h1>Menza U4 bez laktózy</h1>
<div class="meta">Jídelníček UTB na nadcházející týden · aktualizováno {aktualizace}</div>
<div class="legenda"><span>🟢 bez mléčných výrobků</span><span>🟡 může obsahovat skryté mléko – zeptej se</span><span>🔴 obsahuje mléčné výrobky</span></div>
<p class="upozorneni">Hodnocení odhaduje AI jen podle názvů jídel, menza alergeny nezveřejňuje. Před objednáním si složení ověř v kuchyni.</p>
{obsah}
<p class="upozorneni">Automaticky každou neděli ve 13:00 · zdroj: <a href="https://jidelnicek.utb.cz/webkredit/Ordering/Menu">jidelnicek.utb.cz</a></p>
</main></body></html>
"""


def main():
    ted = datetime.now(PRAHA)
    dny = [d for d in stahni_jidelnicek() if d["datum"] > ted.date()]  # jen dny od zítřka
    jidla = [j for d in dny for j in d["jidla"]]
    if jidla:
        ohodnot(jidla)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(vyrob_html(dny, ted.strftime("%-d. %-m. %Y %H:%M")))
    print(f"Ohodnoceno {len(jidla)} jídel na {len(dny)} dní.")


if __name__ == "__main__":
    main()
