import os
import json
from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException

app = Flask(__name__)

# CONFIGURACIÓN ELITE: Conexión optimizada con Binance
def get_binance_client():
    api_key = os.environ.get('dv1my2e5YyXWaWkHduGjw9hfonDJvKVonwIjrzkQKmYRVrmDojmgY6w1kzQEQb5G')
    api_secret = os.environ.get('4AozWEGVrx4qZU4DbG5gO8QVFBQjxrswIUbDTj4f9wCAQ90UD3M6bugKPI25IIO8')
    return Client(api_key, api_secret, {"timeout": 20})

@app.route('/')
def health_check():
    return """
    <body style="font-family:sans-serif; text-align:center; background:#0b0e11; color:#ead196; padding-top:100px;">
        <h1 style="font-size:3em; color:#f0b90b;">⚡ CITERABOT SUPREME v4.0</h1>
        <div style="border:2px solid #f0b90b; display:inline-block; padding:30px; border-radius:15px; background:#1e2329;">
            <p style="font-size:1.5em;">ESTADO: <span style="color:#02c39a;">● ONLINE (EUROPA)</span></p>
            <p>Listo para ejecutar órdenes en <strong>XRPUSDT</strong></p>
        </div>
        <p style="margin-top:20px; color:#707a8a;">Conectado a Binance vía API Segura</p>
    </body>
    """, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. FUERZA BRUTA: Captura el mensaje sin importar el error de TradingView
    try:
        # Intentamos capturar los datos de cualquier forma posible
        raw_data = request.get_data(as_text=True)
        print(f"📥 SEÑAL BRUTA RECIBIDA: {raw_data}")
        
        if request.is_json:
            data = request.get_json()
        else:
            data = json.loads(raw_data)
    except Exception as e:
        # Si TradingView envía basura, intentamos rescatar los campos
        print(f"⚠️ Formato no estándar detectado, rescatando datos...")
        data = request.form.to_dict() or {}

    if not data:
        return jsonify({"status": "error", "message": "Cuerpo vacío"}), 400

    # 2. LIMPIEZA QUIRÚRGICA: Evita errores por espacios o minúsculas
    try:
        action = str(data.get('action', '')).strip().upper()
        symbol = str(data.get('symbol', 'XRPUSDT')).strip().upper().replace(" ", "")
        quantity = float(data.get('quantity', 0))
    except Exception as e:
        print(f"❌ Error de conversión: {e}")
        return jsonify({"status": "error", "message": "Datos numéricos inválidos"}), 400

    # 3. SEGURIDAD DE EJECUCIÓN
    if action not in ['BUY', 'SELL'] or quantity <= 0:
        print(f"❌ Validación fallida: {action} | {quantity}")
        return jsonify({"status": "error", "message": "Instrucción incompleta"}), 400

    # 4. MOTOR DE ALTA VELOCIDAD BINANCE
    try:
        client = get_binance_client()
        print(f"🚀 ENVIANDO A BINANCE -> {action} {quantity} {symbol}")
        
        order = client.create_order(
            symbol=symbol,
            side=action,
            type='MARKET',
            quantity=quantity
        )
        
        print(f"✅ ¡ÉXITO TOTAL! Orden ID: {order.get('orderId')}")
        return jsonify({"status": "success", "order": order}), 200

    except BinanceAPIException as e:
        print(f"❌ ERROR DE BINANCE: {e.message}")
        return jsonify({"status": "error", "message": e.message}), 400
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {str(e)}")
        return jsonify({"status": "error", "message": "Fallo interno"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
