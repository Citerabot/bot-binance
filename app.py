import os, json, urllib.request
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURACIÓN ULTRA PRO + KILLZONES ---
APALANCAMIENTO = 5
RIESGO_CUENTA_PCT = 0.05   
DISTANCIA_SL_PCT = 0.05    
CALLBACK_RATE = 2.0        

# ⏱️ FILTRO DE TIEMPO (Smart Money Killzones)
ACTIVAR_KILLZONES = True
# Horas en formato UTC (Servidor). 
# Rango 1 (Londres): 07:00 a 11:00 UTC -> (02:00 AM a 06:00 AM UTC-5)
# Rango 2 (NY): 12:00 a 16:00 UTC -> (07:00 AM a 11:00 AM UTC-5)
KILLZONES_UTC = [(7, 11), (12, 16)]
# -------------------------------------------

API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
client = Client(API_KEY, API_SECRET)

def get_precision(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return int(s['quantityPrecision']), int(s['pricePrecision'])
    return 0, 0

@app.route('/webhook', methods=['POST'])
def webhook():
    raw_data = request.get_data(as_text=True)
    print(f"📥 SEÑAL RECIBIDA: {raw_data}", flush=True)

    try:
        inicio = raw_data.find('{')
        fin = raw_data.rfind('}') + 1
        data = json.loads(raw_data[inicio:fin])
        
        action = data.get('action', '').upper()
        symbol = data.get('symbol', '').upper()
        
        qty_precision, price_precision = get_precision(symbol)
        client.futures_change_leverage(symbol=symbol, leverage=APALANCAMIENTO)

        # ⏱️ VALIDACIÓN DE HORARIO (Solo restringe entradas, no salidas)
        if ACTIVAR_KILLZONES and action in ['BUY', 'SELL']:
            hora_utc_actual = datetime.utcnow().hour
            en_horario = any(inicio <= hora_utc_actual < fin for inicio, fin in KILLZONES_UTC)
            
            if not en_horario:
                print(f"⏳ FUERA DE KILLZONE (Hora Servidor: {hora_utc_actual}:00 UTC). Señal {action} ignorada para evitar lateralidad.", flush=True)
                return jsonify({"status": "ignored", "reason": "Outside Volatility Killzone"}), 200

        # 🧹 Limpiar terreno si es una nueva entrada válida o un cierre
        client.futures_cancel_all_open_orders(symbol=symbol)

        current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
        quantity = 0

        if action in ['BUY', 'SELL']:
            balances = client.futures_account_balance()
            usdt_balance = next((float(asset['balance']) for asset in balances if asset['asset'] == 'USDT'), 0)
            
            if usdt_balance <= 0:
                raise ValueError("No hay saldo USDT disponible.")

            riesgo_usdt = usdt_balance * RIESGO_CUENTA_PCT
            distancia_sl_precio = current_price * DISTANCIA_SL_PCT
            raw_qty = riesgo_usdt / distancia_sl_precio
            quantity = round(raw_qty, qty_precision)

        # --- EJECUCIÓN ---
        if action == 'BUY':
            sl_price = round(current_price * (1 - DISTANCIA_SL_PCT), price_precision)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=quantity)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=quantity, reduceOnly=True)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type='TRAILING_STOP_MARKET', callbackRate=CALLBACK_RATE, quantity=quantity, reduceOnly=True)
            print(f"✅ LONG DENTRO DE KILLZONE: {quantity} XRP. 🛡️ SL Fijo en {sl_price} | 🏄‍♂️ Trailing al {CALLBACK_RATE}%", flush=True)

        elif action == 'SELL':
            sl_price = round(current_price * (1 + DISTANCIA_SL_PCT), price_precision)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=quantity)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=quantity, reduceOnly=True)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type='TRAILING_STOP_MARKET', callbackRate=CALLBACK_RATE, quantity=quantity, reduceOnly=True)
            print(f"✅ SHORT DENTRO DE KILLZONE: {quantity} XRP. 🛡️ SL Fijo en {sl_price} | 🏄‍♂️ Trailing al {CALLBACK_RATE}%", flush=True)

        elif action == 'CLOSE_LONG':
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 LONG CERRADO", flush=True)

        elif action == 'CLOSE_SHORT':
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 SHORT CERRADO", flush=True)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ INFO/ERROR: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
