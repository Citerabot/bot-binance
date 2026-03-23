import os
import json
from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException

app = Flask(__name__)

# =========================================================
# 🔑 COLOCA TUS CLAVES DE BINANCE AQUÍ ABAJO
# =========================================================
API_KEY = "dv1my2e5YyXWaWkHduGjw9hfonDJvKVonwIjrzkQKmYRVrmDojmgY6w1kzQEQb5G"
API_SECRET = "4AozWEGVrx4qZU4DbG5gO8QVFBQjxrswIUbDTj4f9wCAQ90UD3M6bugKPI25IIO8"
# =========================================================

def get_binance_client():
    return Client(API_KEY, API_SECRET)

@app.route('/')
def index():
    return """
    <body style="font-family:sans-serif; text-align:center; background:#0b0e11; color:#f0b90b; padding-top:100px;">
        <h1 style="font-size:3em;">⚡ CITERABOT v7.0 (ANTI-415)</h1>
        <div style="border:2px solid #f0b90b; display:inline-block; padding:30px; border-radius:15px; background:#1e2329;">
            <p style="color:#02c39a; font-size:1.5em;">● SISTEMA CONECTADO</p>
            <p style="color:white;">Las claves están listas.</p>
        </div>
    </body>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    # 🚀 LA SOLUCIÓN AL ERROR 415: Ignoramos la etiqueta de TradingView
    try:
        # Leemos el mensaje a la fuerza, sin importar la etiqueta que traiga
        raw_data = request.get_data(as_text=True)
        print(f"📥 SEÑAL RECIBIDA DE TRADINGVIEW: {raw_data}")
        
        # Convertimos el texto en un comando que el bot entienda
        inicio = raw_data.find('{')
        fin = raw_data.rfind('}') + 1
        texto_limpio = raw_data[inicio:fin]
        data = json.loads(texto_limpio)
    except Exception as e:
        print(f"❌ Error al intentar leer el paquete: {str(e)}")
        return jsonify({"error": "No se pudo leer"}), 400

    if not data:
        return jsonify({"error": "Mensaje vacio"}), 400

    # PROCESAMIENTO
    action = str(data.get('action', '')).upper().strip()
    symbol = str(data.get('symbol', 'XRPUSDT')).upper().strip()
    try:
        quantity = float(data.get('quantity', 0))
    except:
        quantity = 0

    # EJECUCIÓN
    if action in ['BUY', 'SELL'] and quantity > 0:
        try:
            client = get_binance_client()
            print(f"🚀 Enviando orden a Binance: {action} {quantity} {symbol}")
            
            order = client.create_order(
                symbol=symbol,
                side=action,
                type='MARKET',
                quantity=quantity
            )
            print(f"✅ ¡ÉXITO TOTAL! Orden ID: {order['orderId']}")
            return jsonify({"status": "success", "id": order['orderId']}), 200
        except BinanceAPIException as e:
            # Aquí veremos si Binance te rechaza por saldo o por otra cosa
            print(f"❌ ERROR DE BINANCE: {e.message}")
            return jsonify({"error": e.message}), 400
        except Exception as e:
            print(f"❌ ERROR CRÍTICO INTERNO: {str(e)}")
            return jsonify({"error": "Fallo interno"}), 500
    
    print("❌ Error: Falta acción (BUY/SELL) o cantidad")
    return jsonify({"error": "Datos invalidos"}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
