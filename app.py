#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backend García del Mar — Sistema de reservas
Optimizaciones:
  - Cliente gspread reusado (singleton, NO se reabre en cada request).
  - Validación robusta del lado servidor (horario, fecha futura, anti-spam básico).
  - Logging con `logging` (no `print`) y rotación.
  - CORS configurable por variable de entorno (no abierto por defecto).
  - Cache headers para estáticos.
  - Lectura de configuración via env vars (12-factor).
  - Rate limiting básico in-memory (suficiente para 1 VPS pequeño).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import threading
from collections import deque
from logging.handlers import RotatingFileHandler

import gspread
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# ───────────────────────── Configuración ─────────────────────────

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
# FRONTEND env var: "frontend" (versión optimizada original) o "frontend-pro" (versión editorial)
FRONTEND     = os.environ.get("FRONTEND", "frontend-pro")
FRONTEND_DIR = os.path.join(BASE_DIR, FRONTEND)

SPREADSHEET_ID   = os.environ.get("GS_SPREADSHEET_ID", "1XPCHdgJ9rNap0kwYwsMgJXOC0BP2Km_l4S9Vzm42TZ4")
CREDENTIALS_PATH = os.environ.get("GS_CREDENTIALS_PATH", os.path.join(BASE_DIR, "credentials.json"))
CORS_ORIGINS     = os.environ.get("CORS_ORIGINS", "*")  # en prod: dominio real
PORT             = int(os.environ.get("PORT", 5000))
HOST             = os.environ.get("HOST", "0.0.0.0")

# Horarios permitidos (en minutos desde medianoche): 12:00-13:30 y 20:00-21:30
ALLOWED_RANGES = ((12 * 60, 13 * 60 + 30), (20 * 60, 21 * 60 + 30))

# Rate limit: máx 5 reservas/minuto por IP (suficiente, evita spam de bots).
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX    = 5

# Cache de archivos estáticos (segundos): 1 día para HTML/CSS/JS, 1 año para assets
CACHE_HTML   = 60 * 60          # 1 hora
CACHE_STATIC = 60 * 60 * 24     # 1 día
CACHE_ASSETS = 60 * 60 * 24 * 30  # 30 días

# ───────────────────────── Logging ─────────────────────────

logger = logging.getLogger("garcia-del-mar")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(
    os.path.join(BASE_DIR, "app.log"),
    maxBytes=1_000_000,
    backupCount=3,
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)
logger.addHandler(logging.StreamHandler())

# ───────────────────────── Google Sheets singleton ─────────────────────────

_gs_lock  = threading.Lock()
_gs_sheet = None  # cache del worksheet

def _get_sheet():
    """Devuelve el worksheet, creando el cliente sólo la primera vez.
    Si la conexión falla, vuelve a intentar en la siguiente llamada."""
    global _gs_sheet
    if _gs_sheet is not None:
        return _gs_sheet
    with _gs_lock:
        if _gs_sheet is not None:  # double-checked locking
            return _gs_sheet
        if not os.path.exists(CREDENTIALS_PATH):
            logger.error("No existe credentials.json en %s", CREDENTIALS_PATH)
            return None
        try:
            gc = gspread.service_account(filename=CREDENTIALS_PATH)
            _gs_sheet = gc.open_by_key(SPREADSHEET_ID).get_worksheet(0)
            logger.info("Cliente gspread inicializado.")
            return _gs_sheet
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error inicializando gspread: %s", exc)
            return None


def _append_reservation(data: dict) -> tuple[bool, str]:
    sheet = _get_sheet()
    if sheet is None:
        return False, "No se pudo conectar con Google Sheets."
    row = [
        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data["nombre"],
        data["telefono"],
        data["fecha"],
        data["hora"],
        data["personas"],
        data.get("notas", ""),
        data.get("turno", ""),
    ]
    try:
        sheet.append_row(row, value_input_option="USER_ENTERED")
        return True, "Reserva guardada."
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error al guardar en Sheets: %s", exc)
        # invalidar para forzar reconexión la próxima vez
        global _gs_sheet
        _gs_sheet = None
        return False, "Error al guardar la reserva."

# ───────────────────────── Validación ─────────────────────────

_PHONE_RE = re.compile(r"^[\d+()\-\s]{6,20}$")
_NAME_RE  = re.compile(r"^.{2,80}$")

def _time_to_minutes(t: str) -> int | None:
    if not isinstance(t, str) or not re.match(r"^\d{1,2}:\d{2}$", t):
        return None
    h, m = (int(x) for x in t.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m

def _is_allowed_time(t: str) -> bool:
    m = _time_to_minutes(t)
    if m is None:
        return False
    return any(a <= m <= b for a, b in ALLOWED_RANGES)

def _validate(data: dict) -> str | None:
    """Devuelve None si todo OK, o mensaje de error."""
    if not isinstance(data, dict):
        return "Payload inválido."
    nombre   = str(data.get("nombre", "")).strip()
    telefono = str(data.get("telefono", "")).strip()
    fecha    = str(data.get("fecha", "")).strip()
    hora     = str(data.get("hora", "")).strip()

    if not _NAME_RE.match(nombre):
        return "Nombre inválido."
    if not _PHONE_RE.match(telefono):
        return "Teléfono inválido."

    # personas
    try:
        personas = int(data.get("personas", 0))
    except (TypeError, ValueError):
        return "Cantidad de personas inválida."
    if not (1 <= personas <= 20):
        return "Personas debe estar entre 1 y 20."

    # fecha futura (incluye hoy)
    try:
        f = dt.date.fromisoformat(fecha)
    except ValueError:
        return "Fecha inválida."
    if f < dt.date.today():
        return "La fecha no puede ser pasada."
    if f > dt.date.today() + dt.timedelta(days=180):
        return "La fecha está demasiado lejos en el futuro."

    if not _is_allowed_time(hora):
        return "Horario no disponible. Horarios: 12:00–13:30 y 20:00–21:30."

    notas = str(data.get("notas", "")).strip()
    if len(notas) > 500:
        return "Notas demasiado largas."

    # Sanitizar y devolver datos limpios
    data["nombre"]   = nombre
    data["telefono"] = telefono
    data["fecha"]    = fecha
    data["hora"]     = hora
    data["personas"] = personas
    data["notas"]    = notas
    data["turno"]    = str(data.get("turno", "")).strip()[:4]
    return None

# ───────────────────────── Rate limit in-memory ─────────────────────────

_rl_lock = threading.Lock()
_rl_hits: dict[str, deque] = {}

def _rate_limited(ip: str) -> bool:
    now = dt.datetime.now().timestamp()
    with _rl_lock:
        q = _rl_hits.setdefault(ip, deque())
        # purgar viejos
        while q and (now - q[0]) > RATE_LIMIT_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT_MAX:
            return True
        q.append(now)
    return False

# ───────────────────────── Flask app ─────────────────────────

app = Flask(__name__)
CORS(app, resources={r"/reservar": {"origins": CORS_ORIGINS}})

# Cache headers para estáticos (alivia mucho la carga al servidor)
@app.after_request
def _add_cache_headers(resp):
    path = request.path
    if path.startswith("/assets/"):
        resp.headers.setdefault("Cache-Control", f"public, max-age={CACHE_ASSETS}, immutable")
    elif path.endswith((".css", ".js")):
        resp.headers.setdefault("Cache-Control", f"public, max-age={CACHE_STATIC}")
    elif path == "/" or path.endswith(".html"):
        resp.headers.setdefault("Cache-Control", f"public, max-age={CACHE_HTML}")
    # Headers de seguridad básicos
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
    return resp

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    # Bloquear path traversal (Flask ya lo hace, pero sumamos defensa)
    if ".." in filename or filename.startswith("/"):
        return ("", 404)
    return send_from_directory(FRONTEND_DIR, filename)

@app.route("/health")
def health():
    return jsonify(status="ok", ts=dt.datetime.now().isoformat())

@app.route("/reservar", methods=["POST"])
def handle_reservation():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if _rate_limited(ip):
        return jsonify(ok=False, error="Demasiadas solicitudes. Intentá en un minuto."), 429

    data = request.get_json(silent=True)
    err = _validate(data) if data is not None else "Payload inválido."
    if err:
        return jsonify(ok=False, error=err), 400

    ok, msg = _append_reservation(data)
    if not ok:
        return jsonify(ok=False, error=msg), 500

    logger.info("Reserva OK ip=%s nombre=%s fecha=%s hora=%s", ip, data["nombre"], data["fecha"], data["hora"])
    return jsonify(ok=True, message="¡Reserva recibida!")

# ───────────────────────── Entry point ─────────────────────────

if __name__ == "__main__":
    # En producción usar: gunicorn -w 2 -b 0.0.0.0:5000 app:app
    logger.info("Servidor de desarrollo en http://%s:%s", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False)
