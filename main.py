import json, schedule, time
from datetime import datetime
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from models import Signal, Setting, Symbols
import concurrent.futures
from database import SessionLocal
from BingXApi_v2 import BingXApi


from setLogger import get_logger
logger = get_logger(__name__)


db = SessionLocal()

with open('config.json') as f:
    config = json.load(f)

api = BingXApi(APIKEY=config['api_key'], SECRETKEY=config['api_secret'], demo=True)


class BingX:
	bot: str = 'Stop' # 'Run'
	timeframe: str = ''
	leverage: int = 10
	trade_value: int = 10
	ema_fast: int = 100
	ema_slow: int = 200
	TP_percent: int = 2
	SL_percent: int = 1
	symbols: list = []
	signal = None


	# def _try(self, method:str, **kwargs):
	# 	try:
	# 		if method == 'getPositions':
	# 			res = api.getPositions(symbol=kwargs.get('symbol'))
	# 		elif method == 'placeOrder':
	# 			symbol = kwargs.get('symbol')
	# 			positionSide = kwargs.get('side')
	# 			price = kwargs.get('price')
	# 			volume = kwargs.get('volume')
	# 			tradeType = kwargs.get('tradeType')
	# 			side = kwargs.get('action')
	# 			stopLossPrice = kwargs.get('stopLossPrice')
	# 			takerProfitPrice = kwargs.get('takerProfitPrice')
	# 			res = api.placeOrder(symbol=symbol, side=side, price=price, volume=volume, 
	# 			tradeType=tradeType, action=action, stopLossPrice=stopLossPrice, takerProfitPrice=takerProfitPrice)
	# 		elif method == 'getBalance':
	# 			res = api.getBalance()
	# 		elif method == "setLeverage":
	# 			symbol = kwargs.get('symbol')
	# 			side = kwargs.get('side')
	# 			leverage = kwargs.get('leverage')
	# 			res = api.setLeverage(symbol=symbol, side=side, leverage=leverage)
	# 			return res
	# 		elif method == "getKlines":
	# 			symbol = kwargs.get('symbol')
	# 			interval = kwargs.get('interval')
	# 			startTime = kwargs.get('startTime')
	# 			endTime = kwargs.get('endTime')
	# 			klines = api.getKlines(symbol=symbol, klineType=interval, startTs=startTime, endTs=endTime)
	# 			res = klines
			
	# 		elif method == "closeAll":
	# 			api.closeAllOrders()
	# 			res = api.closeAllPositions()
			
	# 		if res and res['code']:
	# 			logger.error(f'unSuccess---{method}'+str(res['msg'])) 
	# 			return None
	# 		return res['data']
	# 	except Exception as e:
	# 		logger.exception(f"Exception occurred _try method: {method}" + str(e))


	# def placeOrders(self, **kwargs):
	# 	symbol = kwargs.get('symbol')
	# 	positionSide = kwargs.get('positionSide')
	# 	priceLevels = kwargs.get('priceLevels')
	# 	priceLevel0 = kwargs.get('priceLevel0')
	# 	dtime = kwargs.get('dtime')
	# 	peak2 = kwargs.get('peak2')
	# 	margin = float(Bingx._try(method='getBalance')['account']['balance'])
	# 	if not margin: return None
	# 	margin = margin / int(len(Bingx.symbols))
	# 	data = db.query(Symbols).where(Symbols.symbol==symbol).first()
	# 	# set margin mode
	# 	Bingx._try(method="setMarginMode", symbol=symbol, marginMode=data.marginMode)
	# 	per = (data.vol1, data.vol2, data.vol3)
	# 	leverage = data.leverage
	# 	size = [ round( ((data/(sum(per)))*margin / priceLevel0) * leverage, 4) for data in per]
	# 	Bingx._try(method='setLeverage', symbol=symbol, side=positionSide, leverage=leverage)
	# 	side = "Bid" if positionSide == "Long" else "Ask"
	# 	TP = [priceLevel0, priceLevels[0], priceLevels[1] , priceLevels[2]]
	# 	# placeOrder
	# 	for i, price in enumerate(priceLevels[:-1]):
	# 		Bingx._try(method='placeOrder', symbol=symbol, side=side, price=price, volume=size[i], tradeType="Limit", 
	# 				action="Open", stopLossPrice=priceLevels[-1], takerProfitPrice=TP[i])
			
	# 	self.addSignal(symbol=symbol, side=positionSide, level0=priceLevel0, level1=priceLevels[0], level2=priceLevels[1], 
	# 	 				level3=priceLevels[2], SLPrice=priceLevels[3], vol1=size[0], vol2=size[1], vol3=size[2], dtime=dtime, 
	# 					peak2=peak2)
		
	# 	msg = {"symbol": symbol, "status": "", "time": str(dtime), "side":positionSide, "peak2": str(peak2), "level0": str(priceLevel0),
	#  			 "level1": str(priceLevels[0]),"level2": str(priceLevels[1]), "level3": str(priceLevels[2]), 
	# 			 "SLPrice": str(priceLevels[3]), "vol1": str(size[0]), "vol2": str(size[1]), "vol3": str(size[2])}
	# 	toTelegram(msg)


Bingx = BingX()


def get_signal(symbol, interval):
	klines = api.getKline(symbol=symbol, interval=interval)
	klines = klines['data'][::-1]
	if not klines:
		return None
	df = pd.DataFrame(klines)
	df['time'] = pd.to_datetime(df['time']*1000000)
	df['close'] = pd.to_numeric(df['close'])
	df["GC"] = df.ta.ema(100, append=True) > df.ta.ema(200, append=True)
	print(df.tail(10))
	signal = None
	if df['GC'].values[-1] and not df['GC'].values[-2]:
		signal = "LONG"
	elif not df['GC'].values[-1] and df['GC'].values[-2]:
		signal = "SHORT"
	return signal, df['close'].values[-1]


def check_signal(items):
	try:
		symbol = items[0]
		interval = items[1]
		signal, price = get_signal(symbol, interval)
		signal = Bingx.signal
		if not signal:
			return None
		
		positon = api.getPositions(symbol=symbol)
		position = positon['data']
		if position:
			positon = positon[0]
			if signal == position['positionSide']:
				return None
			api.placeOrder(symbol=symbol, side="SELL", positionSide=f"{position['positionSide']}", tradeType="MARKET", quantity=position['positionAmt'])
			return None

		
		qty = Bingx.trade_value / price
		if signal == "LONG":
			SL = price * (1 - Bingx.SL_percent)
			TP = price * (1 + Bingx.TP_percent)
			side = "BUY"
			positionSide = "LONG"
		elif signal == "SHORT":
			SL = price * (1 + Bingx.SL_percent)
			TP = price * (1 - Bingx.TP_percent)
			side = "SELL"
			positionSide = "SHORT"
		
		api.setLeverage(symbol=symbol, side=positionSide, leverage=Bingx.leverage)

		take_profit = "{\"type\": \"TAKE_PROFIT_MARKET\", \"quantity\": %s,\"stopPrice\": %s,\"price\": %s,\"workingType\":\"MARK_PRICE\"}"% (qty, TP, TP)
		stop_loss = "{\"type\": \" STOP_MARKET\", \"quantity\": %s,\"stopPrice\": %s,\"price\": %s,\"workingType\":\"MARK_PRICE\"}"% (qty, SL, SL)
		res = api.placeOrder(symbol=symbol, side=f"side", positionSide=f"{positionSide}", tradeType="MARKET", quantity=qty, 
					takeProfit=take_profit,
					stopLoss=stop_loss)
		
	except Exception as e:
		logger.exception(str(e))


def schedule_signal():
	try:
		symbols = Bingx.symbols
		min_ = time.gmtime().tm_min
		tf = None

		if Bingx.timeframe == "1min":
			tf = '1m'
		if Bingx.timeframe == "5min" and (min_ % 5 == 0):
			tf = '5m'
		elif Bingx.timeframe == "15min" and (min_ % 15 == 0):
			tf = '15m'
		elif Bingx.timeframe == "30min" and (min_ % 30 == 0):
			tf = '30m'
		elif Bingx.timeframe == "1hour" and (min_ == 0):
			tf = '1h'
		elif Bingx.timeframe == "4hour" and (min_ == 0):
			tf = '4h'
		

		if tf:
			with concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols)+1) as executor:
				items = [(sym, f'{tf}') for sym in symbols]
				executor.map(check_signal, items)
		
	except Exception as e:
		logger.exception(str(e))


def schedule_job():
    schedule.every(1).minutes.at(":02").do(job_func=schedule_signal)

    while True:
        if Bingx.bot == "Stop":
            schedule.clear()
            break
        schedule.run_pending()
        print(time.ctime(time.time()))
        time.sleep(1)