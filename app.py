import os, json, urllib.request, urllib.parse, math, time
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *
from datetime import datetime

app = Flask(__name__)

# ==============================================================================
# 🎮 CONFIGURACIÓN SUPREMA (PARÁMETROS QUANT)
# ==============================================================================
ESCUADRON = {
    'LTCUSDT': {'apalancamiento': 5, 'riesgo_pct': 0.05, 'sl_pct': 0.04, 'trail_pct': 1.5},
    'XRPUSDT': {'apalancamiento': 5, 'riesgo_pct': 0.05, 'sl_pct': 0.05, 'trail_pct': 2.0}
}

# SEGURIDAD (Circuit Breaker)
MAX_VOLATILIDAD_SUDDEN = 0.03  # 3% de movimiento brusco bloquea el bot
LOCKOUT_SISTEMA = {"activo": False, "hora_inicio": 0}
ULTIMOS_PRECIOS = {} # Memoria de volatilidad

ACTIVAR_KILLZONES = True
KILLZONES_UTC = [(7, 11), (12, 16)] # Londres y NY

# Credenciales
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

client = Client(API_KEY, API_SECRET)

# ==============================================================================
# 📡 MOTOR 1: COMUNICACIÓN Y ALERTAS
# ==============================================================================
def enviar_telegram(mensaje):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': mensaje}).encode('utf-8')
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"⚠️ Error Telegram: {e}")

# ==============================================================================
# 📊 MOTOR 2: AUDITORÍA FORENSE (Logs de Análisis)
# ==============================================================================
def registrar_forense(moneda, señal, estado, precio, detalle):
    fecha = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    # FORMATO: FECHA | MONEDA | SEÑAL | ESTADO | PRECIO | JUSTIFICACION_MATEMATICA
    log_line = f"{fecha} | {moneda} | {señal} | {estado} | ${precio} | {detalle}"
    print(log_line, flush=True)
    return log_line

# ==============================================================================
# 🛡️ MOTOR 3: PROTECCIÓN DE CAPITAL (Circuit Breaker)
# ==============================================================================
def verificar_seguridad(symbol, precio_actual):
    global LOCKOUT_SISTEMA
    
    # 1. ¿Estamos en bloqueo de pánico? (Dura 1 hora)
    if LOCKOUT_SISTEMA["activo"]:
        if time.time() - LOCKOUT_SISTEMA["hora_inicio"] < 3600:
            return False, "SISTEMA_BLOQUEADO_POR_PANICO"
        else:
            LOCKOUT_SISTEMA["activo"] = False # Reset tras una hora

    # 2. Detección de Flash Crash / Anomalía
    if symbol in ULTIMOS_PRECIOS:
        cambio_pct = abs(precio_actual - ULTIMOS_PRECIOS[symbol]) / ULTIMOS_PRECIOS[symbol]
        if cambio_pct > MAX_VOLATILIDAD_SUDDEN:
            LOCKOUT_SISTEMA = {"activo": True, "hora_inicio": time.time()}
            msg = f"🚨 CIRCUIT BREAKER ACTIVADO en {symbol}\nDetectado movimiento de {cambio_pct*100:.2f}%\nBot bloqueado por seguridad."
            enviar_telegram(msg)
            return False, f"FLASH_CRASH_DETECTADO_{cambio_pct:.4f}"
    
    ULTIMOS_PRECIOS[symbol] = precio_actual
    return True, "SEGURIDAD_OK"

# ==============================================================================
# ⚔️ MOTOR 4: EJECUCIÓN CUÁNTICA
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = json.loads(request.get_data(as_text=True))
        action, symbol = data.get('action', '').upper(), data.get('symbol', '').upper()
        
        if symbol not in ESCUADRON:
            return jsonify({"status": "error", "message": "Simbolo no autorizado"}), 400

        conf = ESCUADRON[symbol]
        ticker = client.futures_symbol_ticker(symbol=symbol)
        precio = float(ticker['price'])

        # --- CAPA 1: CIRCUIT BREAKER ---
        seguro_ok, motivo_seguridad = verificar_seguridad(symbol, precio)
        if not seguro_ok:
            registrar_forense(symbol, action, "RECHAZADO", precio, motivo_seguridad)
            return jsonify({"status": "panic_lockout"}), 403

        # --- CAPA 2: FILTRO DE HORARIO ---
        if ACTIVAR_KILLZONES and action in ['BUY', 'SELL']:
            h_utc = datetime.utcnow().hour
            if not any(i <= h_utc < f for i, f in KILLZONES_UTC):
                registrar_forense(symbol, action, "IGNORADO", precio, "FUERA_DE_KILLZONE_HORARIA")
                return jsonify({"status": "out_of_hours"}), 200

        # --- CAPA 3: EJECUCIÓN ---
        if action in ['BUY', 'SELL']:
            # Configuración de cuenta
            client.futures_change_leverage(symbol=symbol, leverage=conf['apalancamiento'])
            client.futures_cancel_all_open_orders(symbol=symbol)
            
            # Cálculo de Posición (Gestión de Riesgo)
            bal = next(float(a['balance']) for a in client.futures_account_balance() if a['asset'] == 'USDT')
            q_prec = next(int(s['quantityPrecision']) for s in client.futures_exchange_info()['symbols'] if s['symbol'] == symbol)
            p_prec = next(int(s['pricePrecision']) for s in client.futures_exchange_info()['symbols'] if s['symbol'] == symbol)
            
            qty = math.floor((bal * conf['riesgo_pct'] / (precio * conf['sl_pct'])) * (10**q_prec)) / (10**q_prec)
            sl_price = round(precio * (1 - conf['sl_pct']) if action == 'BUY' else precio * (1 + conf['sl_pct']), p_prec)

            # ÓRDENES
            side, opp = (SIDE_BUY, SIDE_SELL) if action == 'BUY' else (SIDE_SELL, SIDE_BUY)
            client.futures_create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=qty)
            client.futures_create_order(symbol=symbol, side=opp, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=qty, reduceOnly=True)
            client.futures_create_order(symbol=symbol, side=opp, type='TRAILING_STOP_MARKET', callbackRate=conf['trail_pct'], quantity=qty, reduceOnly=True)

            justificacion = f"Riesgo:{conf['riesgo_pct']*100}% | Bal:${bal:.2f} | SL:{conf['sl_pct']*100}%"
            registrar_forense(symbol, action, "EJECUTADO", precio, justificacion)
            enviar_telegram(f"⚡ {action} {symbol}\n✅ Ejecutado exitosamente.\n{justificacion}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        registrar_forense("SYSTEM", "ERROR", "CRASH", 0, str(e))
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
