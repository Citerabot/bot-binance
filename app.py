# ==============================================================================
# PROYECTO AEGIS - VERSION: 2.0.1 "Notional Fix"
# CAMBIO: Forzado de tamaño mínimo de orden a $21 para evitar error de Binance.
# ==============================================================================

# ... (Todo el inicio del código anterior se mantiene igual hasta la parte de Ejecución) ...

        # --- MOTOR 4: EJECUCION (CON PARCHE DE MINIMO NOTIONAL) ---
        if action in ['BUY', 'SELL']:
            client.futures_change_leverage(symbol=symbol, leverage=conf['apalancamiento'])
            client.futures_cancel_all_open_orders(symbol=symbol)
            
            # Obtener Balance y Precisiones
            bal = next(float(a['balance']) for a in client.futures_account_balance() if a['asset'] == 'USDT')
            q_prec = next(int(s['quantityPrecision']) for s in client.futures_exchange_info()['symbols'] if s['symbol'] == symbol)
            p_prec = next(int(s['pricePrecision']) for s in client.futures_exchange_info()['symbols'] if s['symbol'] == symbol)
            
            # --- CALCULO QUANT REVISADO ---
            # 1. Calculamos lo que deberíamos comprar según el riesgo (5%)
            qty_riesgo_usd = bal * conf['riesgo_pct'] / conf['sl_pct'] 
            
            # 2. PARCHE V2.0.1: Si el valor es menor a $21, forzamos el mínimo de Binance
            val_final_usd = max(qty_riesgo_usd, 21.0) 
            
            # 3. Convertimos USD a cantidad de la moneda (LTC o XRP)
            qty = math.floor((val_final_usd / precio) * (10**q_prec)) / (10**q_prec)
            
            sl_price = round(precio * (1 - conf['sl_pct']) if action == 'BUY' else precio * (1 + conf['sl_pct']), p_prec)

            # Órdenes
            side, opp = (SIDE_BUY, SIDE_SELL) if action == 'BUY' else (SIDE_SELL, SIDE_BUY)
            client.futures_create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=qty)
            client.futures_create_order(symbol=symbol, side=opp, type=ORDER_TYPE_STOP_MARKET, stopPrice=sl_price, quantity=qty, reduceOnly=True)
            client.futures_create_order(symbol=symbol, side=opp, type='TRAILING_STOP_MARKET', callbackRate=conf['trail_pct'], quantity=qty, reduceOnly=True)

            justificacion = f"Modo_Minimo_Forzado | Bal:${bal:.2f} | Orden_Total:${val_final_usd:.2f}"
            registrar_forense(symbol, action, "EJECUTADO", precio, justificacion)
            enviar_telegram(f"⚡ {action} {symbol}\n✅ Forzado a $21 (Mínimo Binance)\n{justificacion}")

# ... (El resto del código se mantiene igual) ...
