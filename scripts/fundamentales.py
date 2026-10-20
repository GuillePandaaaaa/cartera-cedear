"""Baja métricas de las empresas detrás de los CEDEARs seguidos (data/tickers-noticias.json)
desde Yahoo Finance (librería yfinance) y las guarda en data/fundamentales.json.
Se actualiza una vez por día. Con --check solo dice si hace falta actualizar (sale con 1 si sí).
Lo corre GitHub Actions; si una empresa falla, conserva lo que había de ella."""
import json, math, sys
from datetime import datetime, timezone, timedelta

AR = timezone(timedelta(hours=-3))
hoy = datetime.now(AR).strftime("%Y-%m-%d")
RUTA = "data/fundamentales.json"

def leer(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto

seguidos = [str(t).upper() for t in leer("data/tickers-noticias.json", [])]
actual = leer(RUTA, {"datos": {}})
# Una vez por día; si se suma un ticker a la lista, se intenta ese mismo día (sin reintentar los que fallan).
nuevos = [t for t in seguidos if t not in actual.get("intentados", [])]

if "--check" in sys.argv:
    sys.exit(1 if actual.get("intento") != hoy or nuevos else 0)

import yfinance as yf

def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def fila(df, nombres):
    """Primer valor no vacío de la columna más reciente para alguno de los nombres de fila."""
    if df is None or getattr(df, "empty", True):
        return None
    for n in nombres:
        if n in df.index:
            for v in df.loc[n].tolist():
                if num(v) is not None:
                    return num(v)
    return None

def metricas(ticker):
    t = yf.Ticker(ticker.replace(".", "-"))
    info = t.info or {}
    precio = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
    d = {
        "nombre": info.get("longName") or info.get("shortName"),
        "tipo": info.get("quoteType"),
        "moneda": info.get("currency"),
        "precio": precio,
        "marketCap": num(info.get("marketCap")) or num(info.get("totalAssets")),
        "eps": num(info.get("trailingEps")),
        "pe": num(info.get("trailingPE")),
        "pb": num(info.get("priceToBook")),
        "margen": num(info.get("profitMargins")),
        "forwardPe": num(info.get("forwardPE")),
        "peg": num(info.get("trailingPegRatio")) or num(info.get("pegRatio")),
        "target": num(info.get("targetMeanPrice")),
        "analistas": info.get("numberOfAnalystOpinions"),
        "beta": num(info.get("beta")) or num(info.get("beta3Year")),
        "fcf": num(info.get("freeCashflow")),
    }
    # Dividend yield: dividendo anual / precio (el campo dividendYield cambió de escala entre versiones).
    div = num(info.get("dividendRate")) or num(info.get("trailingAnnualDividendRate"))
    if div is not None and precio:
        d["divYield"] = div / precio
    elif num(info.get("yield")) is not None:          # ETFs
        d["divYield"] = num(info.get("yield"))
    else:
        d["divYield"] = 0.0 if info.get("quoteType") == "EQUITY" else None
    # Deuda / capital propio: pasivos totales / patrimonio neto (último balance trimestral o anual).
    try:
        for bs in (t.quarterly_balance_sheet, t.balance_sheet):
            pas = fila(bs, ["Total Liabilities Net Minority Interest", "Total Liabilities"])
            pat = fila(bs, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"])
            if pas is not None and pat:
                d["deudaCapital"] = pas / pat
                break
    except Exception as e:
        print(f"  {ticker}: sin balance ({e})")
    # Crecimiento de ingresos proyectado por los analistas: próximo año fiscal (o el actual).
    try:
        re = t.revenue_estimate
        if re is not None and not re.empty and "growth" in re.columns:
            for per, etiqueta in (("+1y", "próximo año fiscal"), ("0y", "año fiscal actual")):
                if per in re.index and num(re.loc[per, "growth"]) is not None:
                    d["revGrowth"] = num(re.loc[per, "growth"])
                    d["revGrowthPer"] = etiqueta
                    break
    except Exception as e:
        print(f"  {ticker}: sin estimación de ingresos ({e})")
    if d.get("revGrowth") is None and num(info.get("revenueGrowth")) is not None:
        d["revGrowth"] = num(info.get("revenueGrowth"))
        d["revGrowthPer"] = "último trimestre vs. año anterior"
    return d

datos = actual.get("datos", {})
ok = 0
for tk in seguidos:
    try:
        m = metricas(tk)
        if not m.get("precio") and not m.get("marketCap"):
            raise ValueError("sin datos")
        m["fecha"] = hoy
        datos[tk] = m
        ok += 1
        print(f"{tk}: OK")
    except Exception as e:
        print(f"ERROR {tk}: {e}")

salida = {"actualizado": hoy if ok else actual.get("actualizado"), "intento": hoy, "intentados": seguidos,
          "fuente": "Yahoo Finance", "datos": datos}
with open(RUTA, "w", encoding="utf-8") as f:
    json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
print(f"Fundamentales: {ok} de {len(seguidos)}")
sys.exit(0 if ok else 1)
