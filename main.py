import json, schedule, time
import pandas as pd
import pandas_ta as ta
from models import Signal
import concurrent.futures
from database import SessionLocal
from BingXApi_v2 import BingXApi
import random


from setLogger import get_logger
logger = get_logger(__name__)


with open('config.json') as f:
    config = json.load(f)

api = BingXApi(APIKEY=config['api_key'], SECRETKEY=config['api_secret'], demo=False)


class BingX:
	bot: str = 'Stop' # 'Run'
	timeframe: str = ''
	leverage: int = 10
	trade_value: int = 10
	ema_fast: int = 100
	ema_slow: int = 200
	TP_percent: float = 2
	SL_percent: float = 1
	symbols: list = []


Bingx = BingX()


def get_signal(symbol, interval):
	klines = api.getKline(symbol=symbol, interval=interval)
	if not klines['data']:
		return None, 0, '0'
	klines = klines['data'][::-1]
	
	df = pd.DataFrame(klines)
	print(df.head(5))
	df['time'] = pd.to_datetime(df['time']*1000000)
	df['close'] = pd.to_numeric(df['close'])
	df["GC"] = df.ta.ema(int(Bingx.ema_fast), append=True) > df.ta.ema(int(Bingx.ema_slow), append=True)
	print(df.tail(10))
	signal = None
	if df['GC'].values[-1] and not df['GC'].values[-2]:
		signal = "LONG"
	elif not df['GC'].values[-1] and df['GC'].values[-2]:
		signal = "SHORT"
	return signal, df['close'].iat[-1], str(df['time'].iat[-1])


def check_signal(items):
	try:
		time.sleep(0.1 + random.randint(0, 5)/100)
		symbol = items[0]
		interval = items[1]
		signal, price, time_ = get_signal(symbol, interval)

		logger.info(f"signal: {signal}, price: {price}, time: {time_}")
		if not signal:
			return None
		
		positon = api.getPositions(symbol=symbol)
		position = positon['data']
		if position:
			logger.info("position exist:  "+str(position))
			if signal == position[0]['positionSide']:
				return None
			res = api.placeOrder(symbol=symbol, side="SELL", positionSide=f"{position[0]['positionSide']}", tradeType="MARKET", quantity=position[0]['positionAmt'])
			logger.info(f"{res}")
			return None

		
		qty = Bingx.trade_value / price
		if signal == "LONG":
			SL = price * (1 - Bingx.SL_percent/100)
			TP = price * (1 + Bingx.TP_percent/100)
			side = "BUY"
			positionSide = "LONG"
		elif signal == "SHORT":
			SL = price * (1 + Bingx.SL_percent/100)
			TP = price * (1 - Bingx.TP_percent/100)
			side = "SELL"
			positionSide = "SHORT"
		
		res = api.setLeverage(symbol=symbol, side=positionSide, leverage=Bingx.leverage)
		logger.info(f"set leverage {res}")

		take_profit = "{\"type\": \"TAKE_PROFIT_MARKET\", \"quantity\": %s,\"stopPrice\": %s,\"price\": %s,\"workingType\":\"MARK_PRICE\"}"% (qty, TP, TP)
		stop_loss = "{\"type\": \"STOP_MARKET\", \"quantity\": %s,\"stopPrice\": %s,\"price\": %s,\"workingType\":\"MARK_PRICE\"}"% (qty, SL, SL)
		res = api.placeOrder(symbol=symbol, side=f"{side}", positionSide=f"{positionSide}", tradeType="MARKET", quantity=qty, 
					takeProfit=take_profit,
					stopLoss=stop_loss)
		logger.info(f"new position {res}")
		
		signal = Signal()
		signal.symbol = symbol
		signal.side = side
		signal.price = price
		signal.time = time_
		db = SessionLocal()
		db.add(signal)
		db.commit()
		db.close()
		logger.info(f"add signal: {symbol}-{side}-{price}-{time_}")
		

	except Exception as e:
		logger.exception(str(e))



def schedule_signal():
	try:
		symbols = Bingx.symbols
		min_ = time.gmtime().tm_min
		tf = None

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