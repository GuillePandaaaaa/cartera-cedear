"""Guarda los datos históricos que usa la app:

- data/dolar.json: cotización actual (dolarapi.com) e histórico diario de oficial, MEP (bolsa)
  y CCL (argentinadatos.com). El histórico se vuelve a bajar una vez por día.
- data/hist/<TICKER>.json: cierre diario de cada CEDEAR en pesos ([["AAAA-MM-DD", precio], ...]),
  desde el 25/09/2026. Se toma de data/mercado.json después del cierre (17 h). La primera vez,
  los tickers de data/tickers-noticias.json se completan con data912 historical.

Lo corre GitHub Actions después de scripts/actualizar.py. Si una fuente falla, deja lo que había."""
import json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta

AR = timezone(timedelta(hours=-3))
ahora = datetime.now(AR)
hoy = ahora.strftime("%Y-%m-%d")
DESDE = "2026-09-25"           # las posiciones que Guille ya tenía cuentan desde acá
GUARDAR_DIAS = 400             # los históricos por CEDEAR guardan algo más de un año

def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 cartera-cedear"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)

def num(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None

def leer(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto

def escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))

ok = True

# ---------- Dólar ----------
CASAS = {"oficial": "oficial", "bolsa": "mep", "contadoconliqui": "ccl"}
dolar = leer("data/dolar.json", {})
try:
    actual = {}
    for it in bajar("https://dolarapi.com/v1/dolares"):
        clave = CASAS.get(str(it.get("casa", "")).lower())
        if clave and num(it.get("venta")):
            actual[clave] = {"compra": num(it.get("compra")), "venta": num(it.get("venta")),
                             "fecha": it.get("fechaActualizacion")}
    if not actual:
        raise ValueError("dolarapi sin datos")
    dolar["actual"] = actual
    dolar["fechaActual"] = ahora.strftime("%d/%m/%Y %H:%M")
    print("Dólar actual:", {k: v["venta"] for k, v in actual.items()})
except Exception as e:
    print("ERROR dólar actual:", e); ok = False

try:
    if dolar.get("fechaHist") != hoy or not dolar.get("fechas"):
        series = {}
        for casa, clave in CASAS.items():
            filas = bajar(f"https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}")
            s = {}
            for f in filas:
                d, v = str(f.get("fecha", ""))[:10], num(f.get("venta"))
                if len(d) == 10 and v:
                    s[d] = v
            if len(s) < 100:
                raise ValueError(f"{casa}: muy pocos datos ({len(s)})")
            series[clave] = s
        fechas = sorted(set().union(*[s.keys() for s in series.values()]))
        dolar["fechas"] = fechas
        for clave, s in series.items():
            dolar[clave] = [s.get(d) for d in fechas]
        dolar["fechaHist"] = hoy
        print("Dólar histórico:", len(fechas), "días, hasta", fechas[-1])
    # El último dato del día sale de la cotización actual (el histórico se completa al día siguiente).
    if dolar.get("fechas") and dolar.get("actual") and ahora.weekday() < 5:
        if dolar["fechas"][-1] != hoy:
            dolar["fechas"].append(hoy)
            for clave in CASAS.values():
                dolar.setdefault(clave, [None] * (len(dolar["fechas"]) - 1)).append(None)
        for clave in CASAS.values():
            v = (dolar["actual"].get(clave) or {}).get("venta")
            if v:
                dolar[clave][-1] = v
except Exception as e:
    print("ERROR dólar histórico:", e); ok = False

if dolar:
    escribir("data/dolar.json", dolar)

# ---------- Cierres diarios por CEDEAR ----------
os.makedirs("data/hist", exist_ok=True)
corte = (ahora - timedelta(days=GUARDAR_DIAS)).strftime("%Y-%m-%d")

def guardar_hist(t, puntos):
    pts = sorted((d, round(v, 2)) for d, v in puntos.items() if d >= max(DESDE, corte))
    ruta = f"data/hist/{t}.json"
    nuevo = [list(p) for p in pts]
    if leer(ruta, None) != nuevo:
        escribir(ruta, nuevo)

def hist_de(t):
    return {d: v for d, v in leer(f"data/hist/{t}.json", [])}

# 1) Completar desde data912 los tickers seguidos que todavía no tienen el arranque.
seguidos = [str(t).upper() for t in leer("data/tickers-noticias.json", [])]
for t in seguidos:
    h = hist_de(t)
    if h and min(h) <= DESDE:
        continue
    try:
        filas = bajar(f"https://data912.com/historical/cedears/{t}")
        if not isinstance(filas, list):      # data912 no tiene histórico de algunos papeles (VZ, PG, O)
            print(f"Histórico {t}: data912 no lo tiene; se arma con los cierres diarios")
            continue
        for f in filas:
            if not isinstance(f, dict):
                continue
            d, c = str(f.get("date", ""))[:10], num(f.get("c"))
            if len(d) == 10 and c and d >= DESDE and d not in h:
                h[d] = c
        guardar_hist(t, h)
        print(f"Histórico {t}: {len(h)} días")
    except Exception as e:
        print(f"ERROR histórico {t}:", e); ok = False

# 2) Después del cierre (17 h, días hábiles), sumar el precio del día de todos los CEDEARs.
if ahora.weekday() < 5 and ahora.hour >= 17:
    mercado = leer("data/mercado.json", {})
    fpx = str(mercado.get("fechaPx", ""))           # "dd/mm/aaaa hh:mm"
    if fpx[:10] == ahora.strftime("%d/%m/%Y"):
        for t, px in (mercado.get("precios") or {}).items():
            if num(px) and "/" not in t:
                h = hist_de(t)
                h[hoy] = num(px)
                guardar_hist(t, h)
        print("Cierres del día guardados:", hoy)

sys.exit(0 if ok else 1)
