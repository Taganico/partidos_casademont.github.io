#!/usr/bin/env python3
"""Actualiza resultados y clasificaciones del Casademont Zaragoza."""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).parent
DATOS = AQUI / "datos.json"
CLASIFICACION = AQUI / "clasificacion.json"
MANUAL = AQUI / "manual.json"

URL_ACB = "https://www.acb.com/es/liga/equipos/casademont-zaragoza-16/partidos"
URL_CLAS_ACB = "https://as.com/resultados/baloncesto/acb/2026_2027/clasificacion/"
URL_LF = "https://www.feb.es/lfendesa/resultados.aspx"
URL_CLAS_LF = "https://www.feb.es/lfendesa/clasificacion.aspx"

EQ = "Casademont Zaragoza"


def descargar(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as respuesta:
        return respuesta.read().decode("utf-8", "replace")


def a_texto(html):
    html = re.sub(
        r"(?is)<(script|style).*?</\1>",
        " ",
        html
    )
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip()


def parse_acb(texto):
    """Resultados ACB: {jornada: (local, visitante)}."""
    resultados = {}

    trozos = re.split(
        r"(?<=\s)(?=\d{1,2} Liga Regular)",
        texto
    )

    for trozo in trozos:
        partido = re.match(
            r"(\d{1,2}) Liga Regular\s*LR\s+.*?"
            r"\s(\d{1,3}) - (\d{1,3})\s",
            trozo + " "
        )

        if partido:
            jornada = int(partido.group(1))
            local = int(partido.group(2))
            visitante = int(partido.group(3))
            resultados[jornada] = (local, visitante)

    return resultados


def parse_lf(texto):
    """Lee fecha, hora y marcador desde la web oficial de la FEB."""
    partidos_feb = []

    patron = re.compile(
        r"Día:\s*(\d{2}/\d{2}/\d{4})\s*/\s*"
        r"Hora:\s*(\d{1,2}:\d{2})\s+"
        r"(.*?)(?=Día:\s*\d{2}/\d{2}/\d{4}|$)",
        re.IGNORECASE
    )

    for coincidencia in patron.finditer(texto):
        fecha_feb = coincidencia.group(1)
        hora_feb = coincidencia.group(2)
        bloque = coincidencia.group(3)

        if EQ.lower() not in bloque.lower():
            continue

        marcador = re.search(
            r"(\d{1,3})\s*-\s*(\d{1,3})",
            bloque
        )

        dia, mes, ano = fecha_feb.split("/")

        partido = {
            "d": f"{ano}-{mes}-{dia}",
            "t": hora_feb,
            "res": None,
            "bloque": bloque
        }

        if marcador:
            puntos_local = int(marcador.group(1))
            puntos_visitante = int(marcador.group(2))

            # En FEB, 00-00 significa que el partido aún no se ha jugado.
            if puntos_local != 0 or puntos_visitante != 0:
                partido["res"] = (
                    puntos_local,
                    puntos_visitante
                )

        partidos_feb.append(partido)

    return partidos_feb

def parse_clas_acb(texto):
    """Clasificación completa de Liga ACB desde AS."""
    equipos = []

    nombres = [
        "Real Madrid",
        "Valencia Basket",
        "La Laguna Tenerife",
        "Barça",
        "Baskonia",
        "Unicaja",
        "Río Breogán",
        "Casademont Zaragoza",
        "Surne Bilbao",
        "UCAM Murcia",
        "FIATC Girona",
        "Joventut Badalona",
        "Monbus Obradoiro",
        "Leyma Coruña",
        "Baxi Manresa",
        "Recoletas Salud Burgos",
        "Morabanc Andorra",
        "Ilerna Lleida"
    ]

    for nombre in nombres:
        patron = re.compile(
            r"(?<!\d)(\d{1,2})\s+"
            + re.escape(nombre) +
            r"(?:\s+\d+)?\s+"
            r"(\d{1,2})\s+"
            r"(\d{1,2})\s+"
            r"(\d{1,2})\s+"
            r"(\d{2,4})\s+"
            r"(\d{2,4})"
        )

        encontrado = patron.search(texto)

        if not encontrado:
            continue

        pf = int(encontrado.group(5))
        pc = int(encontrado.group(6))

        equipos.append({
            "pos": int(encontrado.group(1)),
            "equipo": nombre,
            "pj": int(encontrado.group(2)),
            "pg": int(encontrado.group(3)),
            "pp": int(encontrado.group(4)),
            "pf": pf,
            "pc": pc,
            "dif": pf - pc
        })

    equipos.sort(key=lambda equipo: equipo["pos"])
    return equipos
    
def parse_clas_lf(texto):
    """Clasificación completa de Liga Femenina Endesa."""
    equipos = []

    nombres = [
        "CASADEMONT ZARAGOZA",
        "VALENCIA B.C.",
        "AZULMARINO MALLORCA PALMA",
        "HOZONO GLOBAL JAIRIS",
        "MIRAI EUSKOTREN",
        "BAXI FERROL",
        "IMPULSO 360 ESTEPONA",
        "CADI LA SEU",
        "INVERSUS GERNIKA BIZKAIA",
        "MEINS AVENIDA",
        "INNOVA-TSN LEGANÉS",
        "MOVISTAR ESTUDIANTES",
        "SPAR GIRONA",
        "CELTA FEMXA ZORKA",
        "DURÁN MAQUINARIA ENSINO",
        "KUTXABANK ARASKI"
    ]

    for nombre in nombres:
        patron = re.compile(
            r"(?<!\d)(\d{1,2})\s+"
            + re.escape(nombre) +
            r"\s+(\d{1,2})\s+"
            r"(\d{1,2})\s+"
            r"(\d{1,2})\s+"
            r"(\d{2,4})\s+"
            r"(\d{2,4})\s+"
            r"([+-]?\d+)\s+"
            r"\d{1,3}(?:[.,]\d+)?%"
        )

        encontrado = patron.search(texto)

        if not encontrado:
            continue

        equipos.append({
            "pos": int(encontrado.group(1)),
            "equipo": nombre,
            "pj": int(encontrado.group(2)),
            "pg": int(encontrado.group(3)),
            "pp": int(encontrado.group(4)),
            "pf": int(encontrado.group(5)),
            "pc": int(encontrado.group(6)),
            "dif": int(encontrado.group(7))
        })

    equipos.sort(key=lambda equipo: equipo["pos"])
    return equipos


def aplicar(partidos, competicion, resultados):
    cambios = 0

    # -----------------------------------------
    # LIGA FEMENINA - Fuente oficial FEB
    # Actualiza fecha, hora y resultado
    # -----------------------------------------
    if competicion == "LF":

        for partido in partidos:

            if partido["c"] != "LF":
                continue

            rival = partido.get("riv", "")

            if not rival:
                continue

            for dato in resultados:

                bloque = dato.get("bloque", "")

                # El partido de FEB debe contener
                # Casademont Zaragoza y el rival
                if EQ.lower() not in bloque.lower():
                    continue

                if rival.lower() not in bloque.lower():
                    continue
            # ------------------------------------------------
            # EVITAR CONFUNDIR IDA Y VUELTA CONTRA EL MISMO RIVAL
            # ------------------------------------------------
            fecha_feb = dato.get("d")
            fecha_actual = partido.get("d")

            if fecha_feb and fecha_actual:
                from datetime import datetime

                try:
                    f_feb = datetime.strptime(fecha_feb, "%Y-%m-%d")
                    f_actual = datetime.strptime(fecha_actual, "%Y-%m-%d")

                    diferencia_dias = abs((f_feb - f_actual).days)

                    # Una modificación real de calendario puede mover
                    # un partido unos días, pero no varios meses.
                    if diferencia_dias > 14:
                        continue

                except ValueError:
                    pass
                # -----------------------------
                # ACTUALIZAR FECHA
                # -----------------------------
                nueva_fecha = dato.get("d")

                if nueva_fecha and partido.get("d") != nueva_fecha:
                    print(
                        f"LF J{partido['j']}: "
                        f"fecha {partido.get('d')} -> {nueva_fecha}"
                    )

                    partido["d"] = nueva_fecha
                    cambios += 1

                # -----------------------------
                # ACTUALIZAR HORA
                # -----------------------------
                nueva_hora = dato.get("t")

                if nueva_hora and partido.get("t") != nueva_hora:
                    print(
                        f"LF J{partido['j']}: "
                        f"hora {partido.get('t')} -> {nueva_hora}"
                    )

                    partido["t"] = nueva_hora
                    cambios += 1

                # -----------------------------
                # ACTUALIZAR RESULTADO
                # -----------------------------
                marcador = dato.get("res")

                if marcador and not partido.get("res"):

                    local, visitante = marcador

                    partido["res"] = f"{local}-{visitante}"

                    if partido["cond"] == "Local":
                        gana = local > visitante
                    else:
                        gana = visitante > local

                    partido["bal"] = (
                        "Victoria" if gana else "Derrota"
                    )

                    print(
                        f"LF J{partido['j']}: "
                        f"resultado {local}-{visitante}"
                    )

                    cambios += 1

                # Ya hemos encontrado este partido
                break

        return cambios

    # -----------------------------------------
    # ACB
    # Mantener funcionamiento actual
    # -----------------------------------------
    for partido in partidos:

        if partido["c"] != competicion:
            continue

        if partido.get("res"):
            continue

        if not partido.get("riv"):
            continue

        if partido["j"] not in resultados:
            continue

        if EQ not in (
            partido["loc"],
            partido["vis"]
        ):
            continue

        local, visitante = resultados[partido["j"]]

        if partido["cond"] == "Local":
            gana = local > visitante
        else:
            gana = visitante > local

        partido["res"] = f"{local}-{visitante}"
        partido["bal"] = (
            "Victoria" if gana else "Derrota"
        )

        cambios += 1

        print(
            f"{competicion} J{partido['j']}: "
            f"{partido['loc']} {local}-{visitante} "
            f"{partido['vis']}"
        )

    return cambios


def aplicar_manual(partidos):
    if not MANUAL.exists():
        return 0

    cambios = 0
    manuales = json.loads(
        MANUAL.read_text(encoding="utf8")
    )

    for entrada in manuales:
        for partido in partidos:
            coincide = (
                partido["c"] == entrada["c"]
                and partido["j"] == entrada["j"]
                and not partido.get("res")
                and (
                    not entrada.get("riv")
                    or partido["riv"] == entrada["riv"]
                )
            )

            if not coincide:
                continue

            numeros = re.findall(r"\d+", entrada["res"])[:2]

            if len(numeros) < 2:
                continue

            local, visitante = map(int, numeros)

            if partido["cond"] == "Local":
                gana = local > visitante
            else:
                gana = visitante > local

            partido["res"] = entrada["res"]
            partido["bal"] = "Victoria" if gana else "Derrota"
            cambios += 1

            print(
                f"  + manual {entrada['c']} "
                f"J{entrada['j']}: {entrada['res']}"
            )

    return cambios


def main():
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument(
        "--pos",
        nargs=3,
        metavar=("ACB", "LF", "EU")
    )
    args = argumentos.parse_args()

    datos = json.loads(
        DATOS.read_text(encoding="utf8")
    )

    partidos = datos["partidos"]
    cambios = 0

    fuentes_resultados = (
        ("ACB", URL_ACB, parse_acb, "ACB"),
        ("LF", URL_LF, parse_lf, "LF")
    )

    for nombre, url, parser, competicion in fuentes_resultados:
        try:
            texto_web = a_texto(descargar(url))

            if nombre == "LF":
                print("===== INICIO DIAGNOSTICO LF =====")
                print(texto_web)
                print("===== FIN DIAGNOSTICO LF =====")

            resultados = parser(texto_web)
            print(
                f"{nombre}: {len(resultados)} "
                "resultados leídos"
            )
            cambios += aplicar(
                partidos,
                competicion,
                resultados
            )

        except Exception as error:
            print(
                f"{nombre}: no se pudo actualizar ({error})",
                file=sys.stderr
            )

    cambios += aplicar_manual(partidos)

    if CLASIFICACION.exists():
        clasificacion = json.loads(
            CLASIFICACION.read_text(encoding="utf8")
        )
    else:
        clasificacion = {
            "actualizado": "",
            "ACB": [],
            "LF": [],
            "EU": []
        }

    clasificacion_cambiada = False

    try:
        acb = parse_clas_acb(
            a_texto(descargar(URL_CLAS_ACB))
        )
        print(f"Clasificación ACB: {len(acb)} equipos")

        if acb:
            clasificacion["ACB"] = acb
            clasificacion_cambiada = True

    except Exception as error:
        print(
            f"Clasificación ACB: error ({error})",
            file=sys.stderr
        )

    try:
        lf = parse_clas_lf(
            a_texto(descargar(URL_CLAS_LF))
        )
        print(f"Clasificación LF: {len(lf)} equipos")

        if lf:
            clasificacion["LF"] = lf
            clasificacion_cambiada = True

    except Exception as error:
        print(
            f"Clasificación LF: error ({error})",
            file=sys.stderr
        )

    if clasificacion_cambiada:
        clasificacion["actualizado"] = datetime.now(
            ZoneInfo("Europe/Madrid")
        ).strftime("%d/%m/%Y %H:%M")

        CLASIFICACION.write_text(
            json.dumps(
                clasificacion,
                ensure_ascii=False,
                indent=1
            ),
            encoding="utf8"
        )

        print("clasificacion.json actualizado")

    if args.pos:
        datos["posiciones"] = [
            ["Liga ACB", args.pos[0]],
            ["Liga Femenina", args.pos[1]],
            ["EuroLeague W. (Gr. A)", args.pos[2]]
        ]
        cambios += 1

    if cambios:
        datos["actualizado"] = datetime.now(
            ZoneInfo("Europe/Madrid")
        ).strftime("%d/%m/%Y %H:%M")

        DATOS.write_text(
            json.dumps(
                datos,
                ensure_ascii=False,
                indent=1
            ),
            encoding="utf8"
        )

    else:
        print("Sin cambios en resultados")


if __name__ == "__main__":
    main()
