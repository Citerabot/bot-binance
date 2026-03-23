import os, json, urllib.request
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

# Configuración de Binance
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
client = Client(API_KEY, API_SECRET)

# Imprimir IP para Binance Whitelist
try:
    ip_render = urllib.request.urlopen('https://ident.me').read().decode('utf8')
    print(f"🌐 MI DIRECCION IP DE RENDER ES: {ip_render}", flush=True)
except:
    pass

def get_precision(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return int(s['quantityPrecision'])
    return 0

@app.route('/')
def home():
    return "Bot de FUTUROS encendido y operando al 50% de capital."

@app.route('/webhook', methods=['POST'])
def webhook():
    raw_data = request.get_data(as_text=True)
    print(f"📥 SEÑAL RECIBIDA: {raw_data}", flush=True)

    try:
        # Extraer JSON limpio
        inicio = raw_data.find('{')
        fin = raw_data.rfind('}') + 1
        data = json.loads(raw_data[inicio:fin])
        
        action = data.get('action', '').upper()
        symbol = data.get('symbol', '').upper()
        
        # --- EL RASTREADOR DE USDT ---
        if not data.get('quantity'):
            balances = client.futures_account_balance()
            usdt_balance = 0
            
            # Buscamos específicamente la moneda USDT sin importar el orden
            for asset in balances:
                if asset['asset'] == 'USDT':
                    usdt_balance = float(asset['balance'])
                    break
            
            print(f"💰 SALDO USDT ENCONTRADO: {usdt_balance}", flush=True)
            
            if usdt_balance <= 0:
                raise ValueError("No tienes saldo USDT disponible en la billetera de Futuros.")

            # Obtener precio actual
            price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            
            # Apalancamiento fijo en 5x
            leverage = 5
            
            # Fórmula: (Saldo * 50% * Palanca) / Precio
            raw_qty = (usdt_balance * 0.5 * leverage) / price
            precision = get_precision(symbol)
            quantity = round(raw_qty, precision)
            
            print(f"🧮 CALCULANDO COMPRA: 50% de {usdt_balance} USDT a 5x = {quantity} {symbol}", flush=True)
        else:
            quantity = float(data.get('quantity'))

        # Configurar apalancamiento en Binance
        client.futures_change_leverage(symbol=symbol, leverage=5)

        # Ejecución de Órdenes
        if action == 'BUY':
            order = client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=quantity)
        elif action == 'SELL':
            order = client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=quantity)
        elif action == 'CLOSE_LONG':
            order = client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=quantity, reduceOnly=True)
        elif action == 'CLOSE_SHORT':
            order = client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=quantity, reduceOnly=True)
        else:
            raise ValueError("Acción no reconocida. Debe ser BUY, SELL, CLOSE_LONG o CLOSE_SHORT.")

        print(f"✅ EJECUCIÓN EXITOSA: {action} {quantity} {symbol}", flush=True)
        return jsonify({"status": "success", "order": order}), 200

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
