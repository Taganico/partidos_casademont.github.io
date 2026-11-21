#!/usr/bin/env python3
"""Actualiza datos.json (resultados) para index_V5.html.

Fuentes: ACB (Liga Endesa) y MARCA (Liga Femenina Endesa).
EuroLeague Women y posiciones: se rellenan con manual.json / --pos (ver README).
Solo usa la libreria estandar de Python 3.9+.

Uso:
    python actualizar_datos.py
    python actualizar_datos.py --pos "7.º" "1.º" "1.º"      # posiciones ACB, LF, EU
"""
import argparse, json, re, sys, urllib.request
from html import unescape
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).parent
DATOS = AQUI / "datos.json"
CLASIFICACION = AQUI / "clasificacion.json"
MANUAL = AQUI / "manual.json"
URL_ACB = "https://www.acb.com/es/liga/equipos/casademont-zaragoza-16/partidos"
URL_CLAS_ACB = "https://www.acb.com/es/liga/clasificacion"
URL_LF = "https://www.marca.com/baloncesto/liga-femenina/calendario.html"
URL_CLAS_LF = "https://www.feb.es/lfendesa/clasificacion.aspx"
EQ = "Casademont Zaragoza"


def descargar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def a_texto(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def parse_acb(texto):
    """{jornada: (local, visitante)} con los partidos ya jugados."""
    out = {}
    trozos = re.split(r"(?<=\s)(?=\d{1,2} Liga Regular)", texto)
    for t in trozos:
        m = re.match(r"(\d{1,2}) Liga Regular\s*LR\s+.*?\s(\d{1,3}) - (\d{1,3})\s", t + " ")
        if m:
            out[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return out


def parse_lf(texto):
    out = {}
    for sec in re.split(r"(?=Jornada \d+ - )", texto):
        mj = re.match(r"Jornada (\d+) - ", sec)
        if not mj:
            continue
        j = int(mj.group(1))
        m = re.search(rf"{EQ} (\d{{2,3}})-(\d{{2,3}}) ", sec)          # local
        if m:
            out[j] = (int(m.group(1)), int(m.group(2)))
            continue
        m = re.search(rf" (\d{{2,3}})-(\d{{2,3}}) {EQ}", sec)          # visitante
        if m:
            out[j] = (int(m.group(1)), int(m.group(2)))
    return out

def parse_clas_acb(texto):
    """Extrae la clasificación completa de Liga ACB."""
    equipos = []
    patron = re.compile(
        r"(\d{1,2})\s+([A-Z]{2,4})\s+"
        r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+"
        r"\d{1,3}%\s+(\d{2,4})\s+(\d{2,4})\s+(-?\d+)"
    )

    nombres = {
        "RMB": "Real Madrid",
        "VBC": "Valencia Basket",
        "LLT": "La Laguna Tenerife",
        "BAR": "Barça",
        "BKN": "Kosner Baskonia",
        "BRE": "Río Breogán",
        "CAZ": "Casademont Zaragoza",
        "UNI": "Unicaja",
        "SBB": "Surne Bilbao",
        "UCM": "UCAM Murcia",
        "GIR": "FIATC Girona",
        "JOV": "Asisa Joventut"
    }

    for m in patron.finditer(texto):
        codigo = m.group(2)
        equipos.append({
            "pos": int(m.group(1)),
            "equipo": nombres.get(codigo, codigo),
            "codigo": codigo,
            "pj": int(m.group(3)),
            "pg": int(m.group(4)),
            "pp": int(m.group(5)),
            "pf": int(m.group(6)),
            "pc": int(m.group(7)),
            "dif": int(m.group(8))
        })

    return equipos


def aplicar(partidos, comp, resultados):
    n = 0
    for p in partidos:
        if p["c"] != comp or p.get("res") or p["riv"] == "" or p["j"] not in resultados:
            continue
        if EQ not in (p["loc"], p["vis"]):
            continue
        a, b = resultados[p["j"]]
        gana = a > b if p["cond"] == "Local" else b > a
        p["res"], p["bal"] = f"{a}-{b}", "Victoria" if gana else "Derrota"
        n += 1
        print(f"  + {comp} J{p['j']}: {p['loc']} {a}-{b} {p['vis']}")
    return n


def aplicar_manual(partidos):
    """manual.json: [{"c":"EU","j":5,"riv":"Athinaikos","res":"80-70"}]  (res = local-visitante)."""
    if not MANUAL.exists():
        return 0
    n = 0
    for e in json.loads(MANUAL.read_text(encoding="utf8")):
        for p in partidos:
            if p["c"] == e["c"] and p["j"] == e["j"] and (not e.get("riv") or p["riv"] == e["riv"]) and not p.get("res"):
                a, b = (int(x) for x in re.findall(r"\d+", e["res"])[:2])
                gana = a > b if p["cond"] == "Local" else b > a
                p["res"] = e["res"]
                p["bal"] = "Victoria" if gana else "Derrota"
                n += 1
                print(f"  + manual {e['c']} J{e['j']}: {e['res']}")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", nargs=3, metavar=("ACB", "LF", "EU"))
    args = ap.parse_args()

    datos = json.loads(DATOS.read_text(encoding="utf8"))
    ps = datos["partidos"]
    cambios = 0
    for nombre, url, parser, comp in (("ACB", URL_ACB, parse_acb, "ACB"), ("LF", URL_LF, parse_lf, "LF")):
        try:
            res = parser(a_texto(descargar(url)))
            print(f"{nombre}: {len(res)} resultados leidos")
            cambios += aplicar(ps, comp, res)
        except Exception as e:                      # una fuente caida no debe romper el resto
            print(f"{nombre}: no se pudo actualizar ({e})", file=sys.stderr)
    cambios += aplicar_manual(ps)
    # Actualizar clasificaciones
    clas = {
        "actualizado": datetime.now(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M"),
        "ACB": [],
        "LF": [],
        "EU": []
    }

    try:
        clas["ACB"] = parse_clas_acb(a_texto(descargar(URL_CLAS_ACB)))
        print(f"Clasificación ACB: {len(clas['ACB'])} equipos")
    except Exception as e:
        print(f"Clasificación ACB: no se pudo actualizar ({e})", file=sys.stderr)

    try:
        clas["LF"] = parse_clas_lf(a_texto(descargar(URL_CLAS_LF)))
        print(f"Clasificación LF: {len(clas['LF'])} equipos")
    except Exception as e:
        print(f"Clasificación LF: no se pudo actualizar ({e})", file=sys.stderr)

    CLASIFICACION.write_text(
        json.dumps(clas, ensure_ascii=False, indent=1),
        encoding="utf8"
    )

    
    if args.pos:
        datos["posiciones"] = [["Liga ACB", args.pos[0]], ["Liga Femenina", args.pos[1]],
                               ["EuroLeague W. (Gr. A)", args.pos[2]]]
        cambios += 1
    if cambios:
        datos["actualizado"] = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M")
        DATOS.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf8")
        print(f"datos.json actualizado ({cambios} cambios)")
    else:
        print("Sin cambios")


if __name__ == "__main__":
    main()
