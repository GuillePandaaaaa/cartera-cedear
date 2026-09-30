"""Baja precios de CEDEARs (pesos) y dólar MEP de data912.com y los guarda en data/mercado.json.
Lo corre GitHub Actions. Si una fuente falla, conserva el último dato bueno."""
import json, statistics, sys, urllib.request
from datetime import datetime, timezone, timedelta

RUTA = "data/mercado.json"
AR = timezone(timedelta(hours=-3))

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

with open(RUTA, encoding="utf-8") as f:
    datos = json.load(f)
ahora = datetime.now(AR).strftime("%d/%m/%Y %H:%M")
ok = False

# --- Precios CEDEAR en pesos ---
try:
    lista = bajar("https://data912.com/live/arg_cedears")
    nuevos = {}
    for it in lista:
        t = str(it.get("symbol") or it.get("ticker") or "").strip().upper()
        bid, ask = num(it.get("px_bid")), num(it.get("px_ask"))
        px = num(it.get("c")) or num(it.get("close")) or num(it.get("last")) \
             or ((bid + ask) / 2 if bid and ask else None)
        if t and px:
            nuevos[t] = px
    if len(nuevos) < 50:
        raise ValueError(f"muy pocos precios ({len(nuevos)})")
    with open("data/tickers.json", encoding="utf-8") as f:
        conocidos = set(json.load(f))
    act = {t: p for t, p in nuevos.items() if t in conocidos}
    datos["precios"].update(act)
    datos["fechaPx"] = ahora
    ok = True
    print(f"Precios: {len(act)} actualizados de {len(conocidos)}")
except Exception as e:
    print("ERROR precios:", e)

# --- Dólar MEP ---
try:
    m = bajar("https://data912.com/live/mep")
    items = m if isinstance(m, list) else [m]
    def val(it): return num(it.get("mark")) or num(it.get("close"))
    al30 = [val(i) for i in items if "AL30" in str(i.get("ticker") or i.get("symbol") or "").upper()]
    vals = [v for v in (al30 or [val(i) for i in items]) if v]
    mep = statistics.median(vals)
    if not 300 < mep < 20000:
        raise ValueError(f"MEP fuera de rango: {mep}")
    datos["mep"] = round(mep, 2)
    datos["fechaMep"] = ahora
    ok = True
    print("MEP:", datos["mep"])
except Exception as e:
    print("ERROR MEP:", e)

with open(RUTA, "w", encoding="utf-8") as f:
    json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
sys.exit(0 if ok else 1)
