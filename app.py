from flask import Flask, request, jsonify
from binance.um_futures import UMFutures
from binance.error import ClientError
import logging
import os

# Configuración de logs para ver todo claro en Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- PEGA AQUÍ TUS LLAVES DE BINANCE (¡CON COMILLAS!) ---
API_KEY = 'dv1my2e5YyXWaWkHduGjw9hfonDJvKVonwIjrzkQKmYRVrmDojmgY6w1kzQEQb5G'
API_SECRET = '4AozWEGVrx4qZU4DbG5gO8QVFBQjxrswIUbDTj4f9wCAQ90UD3M6bugKPI25IIO8'

# Conectar con Binance Futuros
client = UMFutures(key=API_KEY, secret=API_SECRET)

@app.route('/')
def home():
    return "🚀 El Bot de Binance está corriendo perfectamente en Europa."

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logging.info(f"--- NUEVA SEÑAL RECIBIDA ---")
        logging.info(f"Datos recibidos desde TradingView: {data}")

        # Extraer los datos de la alerta
        action = data.get('action', '').upper()
        symbol = data.get('symbol', 'XRPUSDT')
        quantity = data.get('quantity', 10)

        # Si TradingView manda algo raro, el bot se protege
        if action not in ['BUY', 'SELL']:
            logging.error(f"❌ Acción no válida o vacía: {action}")
            return jsonify({"error": "Accion invalida. Debe ser BUY o SELL"}), 400

        # --- EJECUTAR LA ORDEN EN BINANCE ---
        logging.info(f"Ejecutando orden: {action} {quantity} {symbol} a PRECIO DE MERCADO")
        
        response = client.new_order(
            symbol=symbol,
            side=action,
            type="MARKET",
            quantity=quantity
        )
        
        logging.info(f"✅ ORDEN EJECUTADA CON ÉXITO. ID de Binance: {response.get('orderId')}")
        return jsonify({"status": "success", "order_id": response.get('orderId')}), 200

    except ClientError as e:
        # Errores que vienen directamente de Binance (ej. saldo insuficiente)
        logging.error(f"❌ ERROR DE BINANCE: {e.error_message}")
        return jsonify({"error": "Error en Binance", "details": e.error_message}), 400
        
    except Exception as e:
        # Errores generales del servidor
        logging.error(f"❌ ERROR INTERNO: {str(e)}")
        return jsonify({"error": "Error interno del servidor", "details": str(e)}), 500

if __name__ == '__main__':
    # Render asigna un puerto de forma dinámica, esta línea es OBLIGATORIA
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
