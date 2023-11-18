from fastapi import FastAPI , Depends
from starlette.background import BackgroundTasks
from sqlalchemy.orm import Session
import uvicorn
from models import  SettingAdmin, SignalAdmin, SymbolAdmin, Symbols, ReportView, Setting, Signal
from database import get_db, engine, Base
from sqladmin import Admin
from setLogger import get_logger
from fastapi.responses import RedirectResponse
from main import Bingx, schedule_job


logger = get_logger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI()
admin = Admin(app, engine)

admin.add_view(ReportView)
admin.add_view(SettingAdmin)
admin.add_view(SignalAdmin)
admin.add_view(SymbolAdmin)


@app.get('/run')
async def run(tasks: BackgroundTasks, db: Session=Depends(get_db)):
    user = db.query(Setting).first()
    Bingx.leverage = user.leverage
    Bingx.trade_value = user.trade_value
    Bingx.ema_fast = user.ema_fast
    Bingx.ema_slow = user.ema_slow
    Bingx.TP_percent = user.TP_percent
    Bingx.SL_percent = user.SL_percent
    Bingx.timeframe = user.timeframe
    symbols = db.query(Symbols).all()
    for sym in symbols:
        Bingx.symbols.append(sym.symbol)
    
    tasks.add_task(schedule_job)
    Bingx.bot = "Run"
    logger.info("Bingx started ... ... ...")
    return  RedirectResponse(url="/admin/home")

@app.get('/stop')
def stop():
    Bingx.bot = "Stop"
    logger.inf("Bingx stoped. ................")
    return  RedirectResponse(url="/admin/home")

@app.get('/closeAll')
def closeAll():
    from main import api
    res = api.closeAllPositions()
    logger.info("Close All Positions." + str(res))
    return  RedirectResponse(url="/admin/home")



@app.get('/positions')
def get_positions(symbol:str):
    from main import api
    res = api.getPositions(symbol=symbol)
    logger.info(f"{res}")

@app.get('/add_signal')
async def add_signal(symbol:str, side:str, price: float, time:str, db: Session=Depends(get_db)):
    signal = Signal()
    signal.symbol = symbol
    signal.side = side
    signal.price = price
    signal.time = time
    db.add(signal)
    db.commit()
    db.close()
    logger.info(f"add signal: {symbol}-{side}-{price}-{time}")

@app.get('/')
async def index():
     return  RedirectResponse(url="/admin/home")



if __name__ == '__main__':
	uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)



