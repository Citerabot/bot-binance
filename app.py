import os, json, urllib.request
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

# --- CONFIGURACIÓN ULTRA PRO: GESTIÓN DE RIESGO DINÁMICA ---
APALANCAMIENTO = 5
RIESGO_CUENTA_PCT = 0.05   # Pierdes MÁXIMO el 5% de tus USDT totales si toca el Stop Loss
DISTANCIA_SL_PCT = 0.05    # Stop Loss Súper Amplio al 5% de distancia (evita amagues)
CALLBACK_RATE = 2.0        # Trailing Stop persiguiendo al 2.0% para asegurar ganancias
# -----------------------------------------------------------

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

        # 🧹 Limpiar terreno
        client.futures_cancel_all_open_orders(symbol=symbol)

        current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
        quantity = 0

        if action in ['BUY', 'SELL']:
            balances = client.futures_account_balance()
            usdt_balance = next((float(asset['balance']) for asset in balances if asset['asset'] == 'USDT'), 0)
            
            if usdt_balance <= 0:
                raise ValueError("No hay saldo USDT disponible.")

            # --- LA FÓRMULA DE WALL STREET ---
            riesgo_usdt = usdt_balance * RIESGO_CUENTA_PCT
            distancia_sl_precio = current_price * DISTANCIA_SL_PCT
            
            raw_qty = riesgo_usdt / distancia_sl_precio
            quantity = round(raw_qty, qty_precision)

            print(f"🧮 CALCULO PRO: Saldo={usdt_balance:.2f} | Riesgo Permitido={riesgo_usdt:.2f} USDT | Comprando {quantity} XRP", flush=True)

        # --- EJECUCIÓN CON TRIPLE BLINDAJE ---
        if action == 'BUY':
            sl_price = round(current_price * (1 - DISTANCIA_SL_PCT), price_precision)
            
            # 1. Entrar al mercado
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=quantity)
            # 2. Escudo de Vida (Stop Loss Amplio Fijo)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=quantity, reduceOnly=True)
            # 3. Escudo de Ganancias (Trailing Stop Dinámico)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type='TRAILING_STOP_MARKET', callbackRate=CALLBACK_RATE, quantity=quantity, reduceOnly=True)
            
            print(f"✅ LONG ULTRA PRO: {quantity} XRP. 🛡️ SL Fijo en {sl_price} | 🏄‍♂️ Trailing al {CALLBACK_RATE}%", flush=True)

        elif action == 'SELL':
            sl_price = round(current_price * (1 + DISTANCIA_SL_PCT), price_precision)
            
            # 1. Entrar al mercado
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=quantity)
            # 2. Escudo de Vida (Stop Loss Amplio Fijo)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=quantity, reduceOnly=True)
            # 3. Escudo de Ganancias (Trailing Stop Dinámico)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type='TRAILING_STOP_MARKET', callbackRate=CALLBACK_RATE, quantity=quantity, reduceOnly=True)
            
            print(f"✅ SHORT ULTRA PRO: {quantity} XRP. 🛡️ SL Fijo en {sl_price} | 🏄‍♂️ Trailing al {CALLBACK_RATE}%", flush=True)

        elif action == 'CLOSE_LONG':
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 LONG CERRADO por TradingView", flush=True)

        elif action == 'CLOSE_SHORT':
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 SHORT CERRADO por TradingView", flush=True)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ INFO/ERROR: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
