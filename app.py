import os
from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException

app = Flask(__name__)

# Configuración de Binance (Usa las variables de entorno de Render)
api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')
binance_client = Client(api_key, api_secret)

@app.route('/')
def index():
    return """
    <body style="font-family:sans-serif; text-align:center; padding-top:50px; background:#121212; color:white;">
        <h1 style="color:#02c39a;">🚀 Bot Operativo en Frankfurt</h1>
        <p>El servidor está despierto y escuchando a TradingView.</p>
        <div style="border:1px solid #333; display:inline-block; padding:20px; border-radius:10px;">
            <p>Ruta del Webhook: <strong>/webhook</strong></p>
            <p>Estado: <span style="color:#02c39a;">🟢 Online</span></p>
        </div>
    </body>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Captura de datos "Fuerza Bruta" para evitar Errores 400
    if request.is_json:
        data = request.get_json()
    else:
        # Si TradingView envía datos como texto o formulario, los convertimos
        data = request.form.to_dict() or {}
        if not data and request.data:
            import json
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                pass

    print(f"--- 📥 SEÑAL RECIBIDA: {data} ---")

    # 2. Extraer y limpiar variables
    try:
        action = data.get('action', '').upper()
        symbol = data.get('symbol', '').upper().replace(" ", "")
        quantity = float(data.get('quantity', 0))
    except Exception as e:
        print(f"❌ Error al procesar datos: {e}")
        return jsonify({"status": "error", "message": "Datos mal formados"}), 400

    # 3. Validar contenido
    if action not in ['BUY', 'SELL'] or not symbol or quantity <= 0:
        print(f"❌ Validación fallida: Acción={action}, Simbolo={symbol}, Cantidad={quantity}")
        return jsonify({"status": "error", "message": "Parámetros inválidos"}), 400

    # 4. Ejecución en Binance con manejo de errores avanzado
    try:
        print(f"⚙️ Enviando orden a Binance: {action} {quantity} {symbol}...")
        
        order = binance_client.create_order(
            symbol=symbol,
            side=action,
            type='MARKET',
            quantity=quantity
        )
        
        print(f"✅ ¡ÉXITO! Orden ejecutada. ID: {order.get('orderId')}")
        return jsonify({"status": "success", "order": order}), 200

    except BinanceAPIException as e:
        print(f"❌ ERROR DE BINANCE: {e.status_code} - {e.message}")
        return jsonify({"status": "error", "message": e.message}), 400
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
