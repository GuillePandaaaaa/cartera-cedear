# Cartera CEDEAR

App (PWA) para seguir una cartera de CEDEARs en pesos y dólares MEP.

- `index.html` — la app completa. Las posiciones se guardan en el celular (localStorage).
- `data/mercado.json` — precios y MEP. Lo actualiza GitHub Actions cada 5 min en horario de mercado (`scripts/actualizar.py`, fuente data912.com).
- `data/dolar.json` — dólar oficial, MEP y CCL (actual de dolarapi.com, histórico diario de argentinadatos.com). `scripts/historicos.py`, mismo Action.
- `data/hist/<TICKER>.json` — cierre diario de cada CEDEAR desde el 25/09/2026, para los rendimientos.
- `data/noticias.json` — noticias resumidas en español; las escribe una tarea programada de Claude cada día hábil a la mañana.
- `data/tickers-noticias.json` — CEDEARs de los que se buscan noticias (y cuyo histórico se completa desde data912).
- Para instalarla: abrir la página en Chrome (Android) → menú ⋮ → Instalar app.
