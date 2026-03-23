import os, json, math, urllib.request
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

# Configuración Pro
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
client = Client(API_KEY, API_SECRET)

def get_precision(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return int(s['quantityPrecision'])
    return 0

@app.route('/webhook', methods=['POST'])
def webhook():
    raw_data = request.get_data(as_text=True)
    try:
        inicio, fin = raw_data.find('{'), raw_data.rfind('}') + 1
        data = json.loads(raw_data[inicio:fin])
        
        action = data.get('action').upper()
        symbol = data.get('symbol').upper()
        
        # --- LÓGICA DE PODER: GESTIÓN DE DINERO ---
        # Si no mandas 'quantity', el bot usa el 50% de tu saldo disponible con 5x de palanca
        if not data.get('quantity'):
            balance = float(client.futures_account_balance()[1]['balance']) # Saldo USDT
            price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            leverage = 5
            # Fórmula: (Saldo * Palanca) / Precio
            raw_qty = (balance * 0.5 * leverage) / price
            precision = get_precision(symbol)
            quantity = round(raw_qty, precision)
        else:
            quantity = data.get('quantity')

        client.futures_change_leverage(symbol=symbol, leverage=5)

        # Ejecución de Órdenes
        if action == 'BUY':
            order = client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=quantity)
        elif action == 'SELL':
            order = client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=quantity)
        elif 'CLOSE' in action:
            side = SIDE_SELL if 'LONG' in action else SIDE_BUY
            order = client.futures_create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=quantity, reduceOnly=True)

        print(f"✅ EJECUCIÓN MAESTRA: {action} {quantity} {symbol}", flush=True)
        return jsonify({"status": "success", "order": order}), 200

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
