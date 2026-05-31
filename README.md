# García del Mar — Web optimizada

Backend Flask + frontend estático para reservas con Google Sheets.

## Estructura

```
WEB_GARCIA_DEL_MAR/
├── app.py                          # Backend Flask (API + estáticos en dev)
├── requirements.txt                # Dependencias Python
├── .env.example                    # Variables de entorno (copiar a .env)
├── .gitignore
├── nginx.conf.example              # Config Nginx para producción
├── garcia-del-mar.service.example  # Unit systemd para gunicorn
├── tools/
│   └── optimize_assets.py          # Re-comprimir imágenes si se agregan nuevas
├── frontend/                       # ── Versión OPTIMIZADA (la que ya tenías)
│   ├── index.html                  #    Layout en cards, simple y directo
│   ├── css/styles.css
│   ├── js/app.js
│   └── assets/
└── frontend-pro/                   # ── Versión EDITORIAL (referencia luxury)
    ├── index.html                  #    Carta como menú impreso, tipografía
    ├── css/styles.css              #    Italiana + Cormorant, dot-leaders,
    ├── js/app.js                   #    stepper, segmented controls, etc.
    └── assets/
```

## Las dos versiones — y cómo elegir cuál servir

El backend sirve **una de las dos versiones** según la variable de entorno `FRONTEND`:

```bash
FRONTEND=frontend     python3 app.py   # versión optimizada original
FRONTEND=frontend-pro python3 app.py   # versión editorial (default)
```

Ambas comparten los mismos assets ya comprimidos y consumen la misma API
`/reservar`. Sólo cambia el front. La versión `frontend-pro` está pensada
como referencia de diseño: tipografía editorial (Italiana + Cormorant),
carta a estilo de menú impreso con dot-leaders y "cinco actos" numerados
en romanos, formulario de reserva con stepper de personas y segmented
control de turno + time-slots dorados, galería asimétrica, kanji 海
decorativo, drop cap. La original (`frontend`) es más directa y cercana
al diseño que ya tenías, sólo que limpia y rápida.

## Desarrollo local (Windows / Mac / Linux)

```bash
# 1) Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Colocar credentials.json en la raíz (NO subir al repo)

# 4) Correr
python3 app.py
# Abrir http://localhost:5000
```

## Producción (VPS Ubuntu) — recomendado

### 1) Subir el proyecto

```bash
sudo mkdir -p /var/www/garcia-del-mar
sudo chown -R $USER:$USER /var/www/garcia-del-mar
# Copiar contenido (sin credentials.json) por scp/rsync/git
```

### 2) Credenciales fuera del repo

```bash
sudo mkdir -p /etc/garcia-del-mar
sudo nano /etc/garcia-del-mar/credentials.json   # pegar el JSON nuevo
sudo chmod 600 /etc/garcia-del-mar/credentials.json
sudo chown www-data:www-data /etc/garcia-del-mar/credentials.json
```

### 3) Variables de entorno

```bash
sudo nano /etc/garcia-del-mar/env
```

Contenido:
```
GS_SPREADSHEET_ID=1XPCHdgJ9rNap0kwYwsMgJXOC0BP2Km_l4S9Vzm42TZ4
GS_CREDENTIALS_PATH=/etc/garcia-del-mar/credentials.json
CORS_ORIGINS=https://tu-dominio.com
HOST=127.0.0.1
PORT=5000
```

### 4) Instalar dependencias y gunicorn

```bash
cd /var/www/garcia-del-mar
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 5) Servicio systemd

```bash
sudo cp garcia-del-mar.service.example /etc/systemd/system/garcia-del-mar.service
sudo mkdir -p /var/log/garcia-del-mar
sudo chown www-data:www-data /var/log/garcia-del-mar
sudo systemctl daemon-reload
sudo systemctl enable --now garcia-del-mar
sudo systemctl status garcia-del-mar
```

### 6) Nginx (sirve estáticos directamente)

```bash
sudo apt install nginx
sudo cp nginx.conf.example /etc/nginx/sites-available/garcia-del-mar
sudo nano /etc/nginx/sites-available/garcia-del-mar   # cambiar tu-dominio.com
sudo ln -s /etc/nginx/sites-available/garcia-del-mar /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 7) HTTPS gratis con Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com
```

## Endpoints

- `GET /` — frontend
- `GET /health` — health check (devuelve `{status:"ok", ts:"…"}`)
- `POST /reservar` — crea reserva (JSON con `nombre, telefono, fecha, hora, personas, notas, turno`)

## Mantenimiento

**Agregar imágenes nuevas a la carta:**
1. Pegar el original en `frontend/assets/`
2. Correr `python3 tools/optimize_assets.py` — convierte a JPG + WebP automáticamente
3. Referenciar en `index.html` con `<picture>`

**Ver logs:**
```bash
sudo journalctl -u garcia-del-mar -f                  # live
tail -f /var/log/garcia-del-mar/access.log            # gunicorn
tail -f /var/www/garcia-del-mar/app.log               # app
```

**Reiniciar tras cambios:**
```bash
sudo systemctl restart garcia-del-mar
```

## Cambios respecto a la versión anterior

| Área              | Antes                                  | Ahora                                   |
|-------------------|----------------------------------------|-----------------------------------------|
| Assets totales    | 26 MB                                  | 5.1 MB (-80%)                           |
| Hero video        | 11 MB                                  | 1 MB (H.264 720p, sin audio)            |
| Conexión Sheets   | Reabierta cada request (~1.5s)         | Singleton (~150ms tras primer request)  |
| Servidor estático | Flask                                  | Nginx                                   |
| Validación        | Mínima                                 | Tel/nombre/fecha futura/horario/longitud|
| Rate limit        | Ninguno                                | 5/min por IP                            |
| CORS              | Abierto                                | Configurable por dominio                |
| Bootstrap         | 200 KB cargados                        | Eliminado (utilidades inlined)          |
| JS                | 2 archivos casi iguales, console.logs  | 1 archivo, sin logs, defer              |
| CSS               | 960 líneas con duplicados              | 425 líneas limpias                      |
| URL del API en JS | `http://127.0.0.1:5000` (rompe en VPS) | Relativa `/reservar`                    |
| Credentials       | En el repo                             | Fuera, vía variable de entorno          |
