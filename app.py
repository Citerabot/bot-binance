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
    # Usamos las claves que escribiste arriba
    return Client(API_KEY, API_SECRET)

@app.route('/')
def index():
    return """
    <body style="font-family:sans-serif; text-align:center; background:#0b0e11; color:#f0b90b; padding-top:100px;">
        <h1 style="font-size:3em;">⚡ CITERABOT v6.0 GOLD</h1>
        <div style="border:2px solid #f0b90b; display:inline-block; padding:30px; border-radius:15px; background:#1e2329;">
            <p style="color:#02c39a; font-size:1.5em;">● SISTEMA CONECTADO</p>
            <p style="color:white;">Las claves se han cargado correctamente.</p>
            <p style="color:#707a8a;">Esperando disparo de TradingView...</p>
        </div>
    </body>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. FUERZA BRUTA: Captura el mensaje incluso si viene con errores de formato
    raw_data = request.get_data(as_text=True)
    print(f"📥 SEÑAL RECIBIDA: {raw_data}")
    
    try:
        # Limpieza de espacios y saltos de línea
        clean_content = raw_data.strip()
        data = json.loads(clean_content)
    except:
        # Si no es JSON puro, intentamos leerlo como formulario de respaldo
        data = request.form.to_dict()

    if not data:
        print("❌ Error: El mensaje llegó vacío")
        return jsonify({"error": "Mensaje vacio"}), 400

    # 2. PROCESAMIENTO DE VARIABLES
    action = str(data.get('action', '')).upper().strip()
    symbol = str(data.get('symbol', 'XRPUSDT')).upper().strip()
    try:
        quantity = float(data.get('quantity', 0))
    except:
        quantity = 0

    # 3. EJECUCIÓN EN BINANCE
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
            print(f"❌ ERROR DE BINANCE: {e.message}")
            return jsonify({"error": e.message}), 400
        except Exception as e:
            print(f"❌ ERROR CRÍTICO: {str(e)}")
            return jsonify({"error": "Fallo de conexion"}), 500
    
    print("❌ Error: Los datos de la alerta no son válidos")
    return jsonify({"error": "Datos invalidos"}), 400

if __name__ == '__main__':
    # Render asigna el puerto automáticamente
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
