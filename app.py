import os
import json
from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException

app = Flask(__name__)

# Configuración Blindada de Binance
def get_binance_client():
    api_key = os.environ.get('dv1my2e5YyXWaWkHduGjw9hfonDJvKVonwIjrzkQKmYRVrmDojmgY6w1kzQEQb5G')
    api_secret = os.environ.get('4AozWEGVrx4qZU4DbG5gO8QVFBQjxrswIUbDTj4f9wCAQ90UD3M6bugKPI25IIO8')
    return Client(api_key, api_secret)

@app.route('/')
def index():
    return """
    <body style="font-family:sans-serif; text-align:center; padding-top:50px; background:#0d1117; color:white;">
        <h1 style="color:#58a6ff;">⚡ CITERABOT v2.0 GOLD</h1>
        <p style="font-size:1.2em;">Estado del Servidor: <span style="color:#3fb950;">🟢 ACTIVO (Frankfurt)</span></p>
        <div style="border:1px solid #30363d; display:inline-block; padding:20px; border-radius:10px; background:#161b22;">
            <p>Webhook URL: <code>/webhook</code></p>
            <p>Monitoreo: <strong>XRPUSDT</strong></p>
        </div>
        <p style="color:#8b949e; margin-top:20px;">Esperando señal de TradingView...</p>
    </body>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Extracción de datos con "Fuerza Bruta" (Ignora errores de formato de TV)
    raw_data = request.data.decode('utf-8')
    data = {}
    
    try:
        if request.is_json:
            data = request.get_json()
        else:
            # Si TV envía texto plano, intentamos convertirlo a JSON manualmente
            data = json.loads(raw_data)
    except Exception:
        # Si falla el JSON, intentamos leerlo como formulario
        data = request.form.to_dict()

    if not data:
        print(f"⚠️ Webhook recibido pero vacío o ilegible: {raw_data}")
        return jsonify({"error": "No data found"}), 400

    print(f"📥 SEÑAL RECIBIDA: {data}")

    # 2. Procesamiento y Limpieza Automática
    try:
        action = str(data.get('action', '')).strip().upper()
        symbol = str(data.get('symbol', '')).strip().upper().replace(" ", "")
        quantity = float(data.get('quantity', 0))
    except Exception as e:
        print(f"❌ Error procesando variables: {e}")
        return jsonify({"error": "Invalid parameters"}), 400

    # 3. Validación de Seguridad
    if action not in ['BUY', 'SELL'] or not symbol or quantity <= 0:
        print(f"❌ Validación fallida. Datos: {action} | {symbol} | {quantity}")
        return jsonify({"error": "Validation failed"}), 400

    # 4. Ejecución en Binance con Reporte de Errores
    try:
        client = get_binance_client()
        print(f"🚀 Ejecutando {action} de {quantity} {symbol}...")
        
        order = client.create_order(
            symbol=symbol,
            side=action,
            type='MARKET',
            quantity=quantity
        )
        
        print(f"✅ ¡ORDEN EXITOSA! ID: {order.get('orderId')}")
        return jsonify({"status": "success", "order_id": order.get('orderId')}), 200

    except BinanceAPIException as e:
        print(f"❌ ERROR DE BINANCE: {e.message}")
        return jsonify({"error": e.message}), 400
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
