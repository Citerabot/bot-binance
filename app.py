import os, json, urllib.request, urllib.parse, math
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *
from datetime import datetime

app = Flask(__name__)

# ==============================================================================
# 🎮 PANEL DE CONTROL MODULAR (Configuración)
# ==============================================================================
ESCUADRON = {
    'LTCUSDT': {'apalancamiento': 5, 'riesgo_cuenta_pct': 0.05, 'distancia_sl_pct': 0.04, 'callback_rate': 1.5},
    'XRPUSDT': {'apalancamiento': 5, 'riesgo_cuenta_pct': 0.05, 'distancia_sl_pct': 0.05, 'callback_rate': 2.0}
}

ACTIVAR_KILLZONES = True
KILLZONES_UTC = [(7, 11), (12, 16)] # Londres y NY (UTC)

# Variables de Entorno
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

client = Client(API_KEY, API_SECRET)

# ==============================================================================
# 📡 MOTOR 1: COMUNICACIÓN (Telegram)
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
# 📐 MOTOR 2: MATEMÁTICAS Y RIESGO
# ==============================================================================
def get_precision(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return int(s['quantityPrecision']), int(s['pricePrecision'])
    return 0, 0

def calcular_posicion(balance, precio, pct_riesgo, pct_sl, precision):
    riesgo_usd = balance * pct_riesgo
    distancia_precio = precio * pct_sl
    raw_qty = riesgo_usd / distancia_precio
    factor = 10 ** precision
    return math.floor(raw_qty * factor) / factor

# ==============================================================================
# 📊 MOTOR 3: INTELIGENCIA DE DATOS (Logs Estructurados)
# ==============================================================================
def registrar_dato(moneda, señal, estado, precio, resultado):
    fecha = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    # Formato: FECHA | MONEDA | SEÑAL | ESTADO | PRECIO | RESULTADO
    log_line = f"{fecha} | {moneda} | {señal} | {estado} | {precio} | {resultado}"
    print(log_line, flush=True)
    return log_line

# ==============================================================================
# ⚔️ MOTOR 4: EJECUCIÓN TÁCTICA
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = json.loads(request.get_data(as_text=True))
        action = data.get('action', '').upper()
        symbol = data.get('symbol', '').upper()
        
        if symbol not in ESCUADRON:
            return jsonify({"status": "error", "message": "Simbolo no autorizado"}), 400

        conf = ESCUADRON[symbol]
        precio = float(client.futures_symbol_ticker(symbol=symbol)['price'])
        q_prec, p_prec = get_precision(symbol)

        # 1. Filtro de Killzone
        if ACTIVAR_KILLZONES and action in ['BUY', 'SELL']:
            hora_actual = datetime.utcnow().hour
            if not any(i <= hora_actual < f for i, f in KILLZONES_UTC):
                registrar_dato(symbol, action, "IGNORADO", precio, "FUERA_DE_HORARIO")
                return jsonify({"status": "ignored"}), 200

        # 2. Gestión de Órdenes
        client.futures_change_leverage(symbol=symbol, leverage=conf['apalancamiento'])
        client.futures_cancel_all_open_orders(symbol=symbol)

        if action in ['BUY', 'SELL']:
            bal = next(float(a['balance']) for a in client.futures_account_balance() if a['asset'] == 'USDT')
            qty = calcular_posicion(bal, precio, conf['riesgo_cuenta_pct'], conf['distancia_sl_pct'], q_prec)
            
            side = SIDE_BUY if action == 'BUY' else SIDE_SELL
            opp_side = SIDE_SELL if action == 'BUY' else SIDE_BUY
            sl_price = round(precio * (1 - conf['distancia_sl_pct']) if action == 'BUY' else precio * (1 + conf['distancia_sl_pct']), p_prec)

            # Ejecutar Mercado
            client.futures_create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=qty)
            # Escudo 1: Stop Loss
            client.futures_create_order(symbol=symbol, side=opp_side, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=qty, reduceOnly=True)
            # Escudo 2: Trailing Stop
            client.futures_create_order(symbol=symbol, side=opp_side, type='TRAILING_STOP_MARKET', callbackRate=conf['callback_rate'], quantity=qty, reduceOnly=True)

            msg = f"🚀 {action} {symbol}\n💰 Qty: {qty}\n🛡️ SL: {sl_price}\n🌊 Trail: {conf['callback_rate']}%"
            enviar_telegram(msg)
            registrar_dato(symbol, action, "EJECUTADO", precio, f"OPEN_{action}")

        elif 'CLOSE' in action:
            # Aquí se puede agregar lógica para cerrar posiciones específicas si es necesario
            registrar_dato(symbol, action, "CERRADO", precio, "EXIT_SIGNAL")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        registrar_dato("ERROR", "SYSTEM", "CRASH", 0, str(e))
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
