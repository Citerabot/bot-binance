import os, json, urllib.request
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

# --- CONFIGURACIÓN DE TU ESTRATEGIA CON DOBLE BLINDAJE ---
APALANCAMIENTO = 5
PORCENTAJE_CAPITAL = 0.50  # Usa el 50% de tu saldo
CALLBACK_RATE = 2.0        # Escudo 1: Trailing Stop al 2.0%
# ---------------------------------------------------------

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

        # 🧹 PASO CLAVE: Cancelar el Trailing Stop pendiente si TradingView manda una orden
        client.futures_cancel_all_open_orders(symbol=symbol)

        quantity = 0
        current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])

        if action in ['BUY', 'SELL']:
            balances = client.futures_account_balance()
            usdt_balance = next((float(asset['balance']) for asset in balances if asset['asset'] == 'USDT'), 0)
            
            if usdt_balance <= 0:
                raise ValueError("No hay saldo USDT disponible.")

            raw_qty = (usdt_balance * PORCENTAJE_CAPITAL * APALANCAMIENTO) / current_price
            quantity = round(raw_qty, qty_precision)

        # EJECUCIÓN
        if action == 'BUY':
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=quantity)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type='TRAILING_STOP_MARKET', callbackRate=CALLBACK_RATE, quantity=quantity, reduceOnly=True)
            print(f"✅ LONG ABIERTO Y BLINDADO (Trailing al {CALLBACK_RATE}%)", flush=True)

        elif action == 'SELL':
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=quantity)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type='TRAILING_STOP_MARKET', callbackRate=CALLBACK_RATE, quantity=quantity, reduceOnly=True)
            print(f"✅ SHORT ABIERTO Y BLINDADO (Trailing al {CALLBACK_RATE}%)", flush=True)

        elif action == 'CLOSE_LONG':
            # Escudo 2: Cierra por cambio de estructura en el indicador
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 LONG CERRADO por cambio de estructura en TradingView", flush=True)

        elif action == 'CLOSE_SHORT':
            # Escudo 2: Cierra por cambio de estructura en el indicador
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 SHORT CERRADO por cambio de estructura en TradingView", flush=True)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ INFO: {str(e)}", flush=True) # Cambiado a INFO porque rechazos de ReduceOnly son normales aquí
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
