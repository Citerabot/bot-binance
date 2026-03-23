import os
import json
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

# Conectar con Binance usando tus variables de entorno en Render
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')

try:
    client = Client(API_KEY, API_SECRET)
    print("✅ Conectado a Binance correctamente", flush=True)
except Exception as e:
    print(f"❌ Error al conectar con Binance: {e}", flush=True)

@app.route('/')
def home():
    return "El bot está encendido y esperando señales."

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Recibir el paquete a la fuerza como texto (Evita el Error 400 de Flask)
    raw_data = request.get_data(as_text=True)
    print(f"📥 SEÑAL RECIBIDA EN CRUDO: {raw_data}", flush=True)

    try:
        # 2. Filtrar la basura de TradingView (Buscar las llaves { } )
        inicio = raw_data.find('{')
        fin = raw_data.rfind('}') + 1
        
        if inicio == -1 or fin == 0:
            raise ValueError("El mensaje no contiene código JSON con llaves {}")
            
        texto_limpio = raw_data[inicio:fin]
        print(f"🧹 TEXTO LIMPIO EXTRAÍDO: {texto_limpio}", flush=True)

        # 3. Traducir a JSON
        data = json.loads(texto_limpio)
        print(f"✅ JSON TRADUCIDO PERFECTO: {data}", flush=True)

        # 4. Extraer los datos para Binance
        action = data.get('action', '').upper()
        symbol = data.get('symbol')
        quantity = data.get('quantity')

        if not symbol or not quantity:
            print("❌ Error: Falta el símbolo o la cantidad en el mensaje.", flush=True)
            return jsonify({"error": "Faltan datos"}), 400

        print(f"🚀 ENVIANDO ORDEN A BINANCE: {action} {quantity} de {symbol}", flush=True)

        # 5. Ejecutar la compra/venta en Binance
        if action == 'BUY':
            order = client.create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
        elif action == 'SELL':
            order = client.create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
        else:
            print("❌ Error: Acción no reconocida (Debe ser BUY o SELL)", flush=True)
            return jsonify({"error": "Acción inválida"}), 400

        # 6. Éxito total
        print(f"🎉 ¡COMPRA EXITOSA EN BINANCE!: {order}", flush=True)
        return jsonify({"status": "success", "order": order}), 200

    except Exception as e:
        print(f"❌ ERROR DURANTE EL PROCESO: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    # Render usa el puerto 10000 por defecto
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
