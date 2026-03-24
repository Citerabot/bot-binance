import os, json, urllib.request, math
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *
from datetime import datetime

app = Flask(__name__)

# ==============================================================================
# 🧠 CEREBRO DEL ESCUADRÓN (CONFIGURACIÓN INDIVIDUAL POR ACTIVO)
# ==============================================================================
ESCUADRON = {
    'BTCUSDT': {'apalancamiento': 5, 'riesgo_cuenta_pct': 0.05, 'distancia_sl_pct': 0.025, 'callback_rate': 1.0},
    'ETHUSDT': {'apalancamiento': 5, 'riesgo_cuenta_pct': 0.05, 'distancia_sl_pct': 0.035, 'callback_rate': 1.5},
    'LTCUSDT': {'apalancamiento': 5, 'riesgo_cuenta_pct': 0.05, 'distancia_sl_pct': 0.040, 'callback_rate': 1.5},
    'XRPUSDT': {'apalancamiento': 5, 'riesgo_cuenta_pct': 0.05, 'distancia_sl_pct': 0.050, 'callback_rate': 2.0}
}

# ⏱️ FILTRO INSTITUCIONAL (Killzones)
ACTIVAR_KILLZONES = True
KILLZONES_UTC = [(7, 11), (12, 16)] # Londres y Nueva York (Hora Servidor UTC)
# ==============================================================================

API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
client = Client(API_KEY, API_SECRET)

def get_precision(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return int(s['quantityPrecision']), int(s['pricePrecision'])
    return 0, 0

def redondear_hacia_abajo(numero, decimales):
    factor = 10 ** decimales
    return math.floor(numero * factor) / factor

@app.route('/webhook', methods=['POST'])
def webhook():
    raw_data = request.get_data(as_text=True)
    print(f"\n[{datetime.utcnow().strftime('%H:%M:%S UTC')}] 📥 SEÑAL RECIBIDA: {raw_data}", flush=True)

    try:
        # Extraer JSON
        inicio = raw_data.find('{')
        fin = raw_data.rfind('}') + 1
        data = json.loads(raw_data[inicio:fin])
        
        action = data.get('action', '').upper()
        symbol = data.get('symbol', '').upper()
        
        # 🛡️ Filtro 1: ¿Pertenece al Escuadrón?
        if symbol not in ESCUADRON:
            print(f"⚠️ {symbol} no está en el Escuadrón. Ignorando.", flush=True)
            return jsonify({"status": "ignored", "reason": "Symbol not assigned"}), 200

        config = ESCUADRON[symbol]
        qty_precision, price_precision = get_precision(symbol)
        
        # Ajustar Apalancamiento automáticamente
        client.futures_change_leverage(symbol=symbol, leverage=config['apalancamiento'])

        # ⏱️ Filtro 2: Killzones (Solo restringe aperturas, NUNCA cierres)
        if ACTIVAR_KILLZONES and action in ['BUY', 'SELL']:
            hora_utc = datetime.utcnow().hour
            en_horario = any(inicio <= hora_utc < fin for inicio, fin in KILLZONES_UTC)
            if not en_horario:
                print(f"⏳ FUERA DE KILLZONE ({hora_utc}:00 UTC). Señal de {symbol} ignorada.", flush=True)
                return jsonify({"status": "ignored", "reason": "Outside Volatility Killzone"}), 200

        # 🧹 Filtro 3: Limpiar el campo de batalla de esta moneda
        client.futures_cancel_all_open_orders(symbol=symbol)

        # 🧮 Lógica Matemática de Riesgo
        current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
        quantity = 0

        if action in ['BUY', 'SELL']:
            balances = client.futures_account_balance()
            usdt_balance = next((float(asset['balance']) for asset in balances if asset['asset'] == 'USDT'), 0)
            
            if usdt_balance <= 0:
                raise ValueError("Cuenta en $0. No hay USDT para operar.")

            # Fórmula Quant: (Capital * %Riesgo) / (Precio * %Distancia_SL)
            riesgo_usdt = usdt_balance * config['riesgo_cuenta_pct']
            distancia_sl_precio = current_price * config['distancia_sl_pct']
            raw_qty = riesgo_usdt / distancia_sl_precio
            
            # Redondeo estricto hacia abajo para que Binance no rechace por exceso de decimales
            quantity = redondear_hacia_abajo(raw_qty, qty_precision)
            print(f"🧮 {symbol} | Capital: {usdt_balance:.2f} | Riesgo: {riesgo_usdt:.2f} USDT | Calculado: {quantity} tokens", flush=True)

        # ⚔️ EJECUCIÓN TÁCTICA ⚔️
        if action == 'BUY':
            sl_price = round(current_price * (1 - config['distancia_sl_pct']), price_precision)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=quantity)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=quantity, reduceOnly=True)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type='TRAILING_STOP_MARKET', callbackRate=config['callback_rate'], quantity=quantity, reduceOnly=True)
            print(f"🟢 LONG {symbol} EJECUTADO. Cant: {quantity} | SL: {sl_price} | Trail: {config['callback_rate']}%", flush=True)

        elif action == 'SELL':
            sl_price = round(current_price * (1 + config['distancia_sl_pct']), price_precision)
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=quantity)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=quantity, reduceOnly=True)
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type='TRAILING_STOP_MARKET', callbackRate=config['callback_rate'], quantity=quantity, reduceOnly=True)
            print(f"🔴 SHORT {symbol} EJECUTADO. Cant: {quantity} | SL: {sl_price} | Trail: {config['callback_rate']}%", flush=True)

        elif action == 'CLOSE_LONG':
            client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 LONG {symbol} CERRADO MANUALMENTE POR INDICADOR", flush=True)

        elif action == 'CLOSE_SHORT':
            client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=float(data.get('quantity', 0)), reduceOnly=True)
            print(f"🛑 SHORT {symbol} CERRADO MANUALMENTE POR INDICADOR", flush=True)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ INFO/ERROR ({symbol if 'symbol' in locals() else 'System'}): {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
