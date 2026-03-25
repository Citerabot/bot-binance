import os
import math
from flask import Flask, request
from binance.client import Client
from binance.enums import *
import requests

app = Flask(__name__)

# ==========================================
# CONFIGURACIÓN DE SEGURIDAD Y VARIABLES
# ==========================================
BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY')
BINANCE_API_SECRET = os.environ.get('BINANCE_API_SECRET')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
PASSPHRASE = "SupremaV60_XRP_2026"

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

# ==========================================
# MOTOR DE COMUNICACIÓN (TELEGRAM)
# ==========================================
def enviar_telegram(mensaje):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def registrar_forense(symbol, action, estado, precio, justificacion):
    print(f"| {symbol} | {action} | {estado} | {precio} | {justificacion} |")

# ==========================================
# CEREBRO QUANT Y EJECUCIÓN
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # 1. Autenticación
    if data.get('passphrase') != PASSPHRASE:
        return {"status": "error", "message": "Acceso denegado"}, 401

    symbol = data['symbol']
    action = data['action']
    precio = data['price']
    
    # 2. Gestión de Riesgo
    conf = {
        'apalancamiento': 10,  # Tu configuración actual
        'riesgo_pct': 0.05,
        'sl_pct': 0.02,
        'trail_pct': 1.5
    }

    try:
        # 3. Lógica de Ejecución (Parche Notional V2.0.1)
        if action in ['BUY', 'SELL']:
            client.futures_change_leverage(symbol=symbol, leverage=conf['apalancamiento'])
            client.futures_cancel_all_open_orders(symbol=symbol)
            
            bal_data = client.futures_account_balance()
            bal = next(float(a['balance']) for a in bal_data if a['asset'] == 'USDT')
            
            info = client.futures_exchange_info()
            q_prec = next(int(s['quantityPrecision']) for s in info['symbols'] if s['symbol'] == symbol)
            p_prec = next(int(s['pricePrecision']) for s in info['symbols'] if s['symbol'] == symbol)
            
            qty_riesgo_usd = bal * conf['riesgo_pct'] / conf['sl_pct'] 
            val_final_usd = max(qty_riesgo_usd, 21.0) # FORZADO MÍNIMO BINANCE
            
            qty = math.floor((val_final_usd / precio) * (10**q_prec)) / (10**q_prec)
            sl_price = round(precio * (1 - conf['sl_pct']) if action == 'BUY' else precio * (1 + conf['sl_pct']), p_prec)

            side = SIDE_BUY if action == 'BUY' else SIDE_SELL
            opp = SIDE_SELL if action == 'BUY' else SIDE_BUY
            
            client.futures_create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=qty)
            client.futures_create_order(symbol=symbol, side=opp, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=qty, reduceOnly=True)
            
            justificacion = f"Modo_Minimo_Forzado | Bal:${bal:.2f} | Orden_Total:${val_final_usd:.2f}"
            registrar_forense(symbol, action, "EJECUTADO", precio, justificacion)
            enviar_telegram(f"⚡ {action} {symbol}\n✅ Ejecutado a ${precio}\n{justificacion}")
            
        return {"status": "success"}, 200

    except Exception as e:
        enviar_telegram(f"⚠️ ERROR en {symbol}: {str(e)}")
        print(f"ERROR FATAL: {str(e)}")
        return {"status": "error", "message": str(e)}, 400

# TEST DE CONEXIÓN
enviar_telegram("🛡️ SISTEMA AEGIS ONLINE\nVersión: 2.0.1\nEstado: Vigilando mercados...")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
