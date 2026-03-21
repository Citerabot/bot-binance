import os
import json
from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException

app = Flask(__name__)

# Configuración Blindada: Las llaves se cargan desde Render (Entorno)
def get_binance_client():
    api_key = os.environ.get('dv1my2e5YyXWaWkHduGjw9hfonDJvKVonwIjrzkQKmYRVrmDojmgY6w1kzQEQb5G')
    api_secret = os.environ.get('4AozWEGVrx4qZU4DbG5gO8QVFBQjxrswIUbDTj4f9wCAQ90UD3M6bugKPI25IIO8')
    return Client(api_key, api_secret)

@app.route('/')
def index():
    return """
    <body style="font-family:sans-serif; text-align:center; padding-top:50px; background:#0d1117; color:white;">
        <h1 style="color:#58a6ff;">⚡ CITERABOT v3.0 SUPREME</h1>
        <p style="font-size:1.2em;">Estado del Servidor: <span style="color:#3fb950;">🟢 ACTIVO (Frankfurt)</span></p>
        <div style="border:1px solid #30363d; display:inline-block; padding:20px; border-radius:10px; background:#161b22;">
            <p>Webhook URL: <code>/webhook</code></p>
            <p>Monitoreo: <strong>XRPUSDT</strong></p>
        </div>
        <p style="color:#8b949e; margin-top:20px;">Escuchando señales de TradingView en tiempo real...</p>
    </body>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. RECEPTOR UNIVERSAL: Extrae datos aunque vengan mal formateados
    data = {}
    try:
        # Intenta leer como JSON puro
        if request.is_json:
            data = request.get_json()
        else:
            # Si TV envía texto plano, forzamos la lectura
            raw_content = request.data.decode('utf-8')
            data = json.loads(raw_content)
    except Exception:
        # Si falla lo anterior, probamos como formulario
        data = request.form.to_dict()

    if not data:
        print(f"⚠️ Webhook vacío o ilegible. Raw: {request.data}")
        return jsonify({"error": "No data found"}), 400

    print(f"📥 SEÑAL RECIBIDA: {data}")

    # 2. PROCESADOR DE ALTA PRECISIÓN (Limpia espacios y mayúsculas)
    try:
        action = str(data.get('action', '')).strip().upper()
        symbol = str(data.get('symbol', '')).strip().upper().replace(" ", "")
        quantity = float(data.get('quantity', 0))
    except Exception as e:
        print(f"❌ Error procesando parámetros: {e}")
        return jsonify({"error": "Invalid format"}), 400

    # 3. FILTRO DE SEGURIDAD
    if action not in ['BUY', 'SELL'] or not symbol or quantity <= 0:
        print(f"❌ Validación fallida para: {action} {symbol} {quantity}")
        return jsonify({"error": "Validation failed"}), 400

    # 4. MOTOR DE EJECUCIÓN BINANCE (Con reporte de errores detallado)
    try:
        client = get_binance_client()
        print(f"🚀 Ejecutando {action} de {quantity} {symbol} en mercado...")
        
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
        # Si el error es por saldo, te lo dirá claramente aquí
        return jsonify({"error": e.message}), 400
    except Exception as e:
        print(f"❌ ERROR CRÍTICO DEL SISTEMA: {str(e)}")
        return jsonify({"error": "Internal error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
