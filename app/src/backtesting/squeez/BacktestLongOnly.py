import pandas as pd
import numpy as np
import pandas_ta as ta
import enum
import math
from BacktestBase import *
from pandas_ta.volatility import kc 

class SLOPE(enum.Enum):
    NEUTRAL = 0
    POSITIVE = 1
    NEGATIVE = 2
    
class POSITION(enum.Enum):
    NEUTRAL = 0
    LONG = 1
    SHORT = 2
    
class EMA25(enum.Enum):
    PRICE_ACCION_NEUTRAL_EMA = 0
    PRICE_ACCION_UNDER_EMA = 1
    PRICE_ACCION_OVER_EMA = 2

class BacktestLongOnly(BacktestBase):
    def __init__(self, symbol, start, end, amount, ftc=0.0, ptc=0.0, verbose=True):

        super().__init__(symbol, start, end, amount, ftc, ptc, verbose)
        
        self.calculateEMA25()
        self.calculateBolingerAndKeltnerChannels(kc)
        self.detectSqueeze()
        self.detectSqueezeCloseToEMA()
        self.isUptrend()
        
    def calculateEMA25(self):
        self.data['ema25'] = self.data['Close'].ewm(span=25, adjust=False).mean()
        
    def calculateBolingerAndKeltnerChannels(self, kc)->None:
        df=self.data
        # Bolinger Bands
        df.ta.bbands(append=True, length=20, std=2)
        
        # Initialize Keltner Channel Indictor
        kc=kc(high=df['High'], low=df['Low'], close=df["Close"], window=20)
        
        #Bolinger Band Upper - Keltner Channel Upper
        df['bbu_minus_kcu'] = df['BBU_20_2.0'] - kc['KCUe_20_2']

    def detectSqueezeCloseToEMA(self, zoneWidth = .10)->None:
        df=self.data
        df['squeezeCloseToEma'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
        
        cond =(
                (df.squeezedArea == EMA25['PRICE_ACCION_OVER_EMA'].value) &
                (
                    (df.Open > df.ema25) & (df.Close > df.ema25)
                ) &
               (
                   (abs(df.Open-df.ema25)<=zoneWidth) | (abs(df.Close-df.ema25)<=zoneWidth)
               )
            )
    
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_OVER_EMA'].value
    
        cond =((df.squeezedArea == EMA25['PRICE_ACCION_UNDER_EMA'].value) & (abs(df.High-df.ema25)<=zoneWidth))
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_UNDER_EMA'].value
    
    def detectSqueeze(self)->None:
        df=self.data
        df['squeezedArea'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
        cond = ((df.bbu_minus_kcu <= 0) & (df.Close < df.ema25))
        df.loc[cond, 'squeezedArea'] = EMA25['PRICE_ACCION_UNDER_EMA'].value
        
        cond2 =((df.bbu_minus_kcu <= 0) & (df.Close > df.ema25))
        df.loc[cond2, 'squeezedArea'] = EMA25['PRICE_ACCION_OVER_EMA'].value

    def isSmaUptrend(sma, N):
        y = sma[-N:] # Check the last N 10 points for uptrend
        x = np.arange(len(y))
        slope = np.polyfit(x, y, 1)[0]
        return slope > 0
    
    def isUptrend(self):
        df=self.data
        df['SMA'] = df['Close'].rolling(window=100).mean()
        
        df['isUptrend'] = False
        if not df['SMA'].dropna().empty:
            if BacktestLongOnly.isSmaUptrend(df['SMA'], 20):
                    df['isUptrend'] = True
                
    def runStrategy(self):
        ''' Backtesting Squeeze Strategy.
        '''
        df=self.data
        #stop = '((close/ema25-1)*100 >=-10)'
        stop = 'close<ema25'
        target = '(current_price-buying_price) >= 1'
        
        msg = f'\n\nRunning Squeeze strategy'
        msg += f'\nstop:   {stop} '
        msg += f'\ntarget: {target} '
        msg += f'\nfixed costs {self.ftc} '
        msg += f'proportional costs {self.ptc}'
        print(msg)
        print('=' * 55)
        self.position = POSITION['NEUTRAL'].value
        self.trades = 0  # no trades yet
        self.amount = self.initial_amount  # reset initial capital
        window = 3
        log = []
        
        for candle in range(0, len(df)):

            ema25 = (df.iloc[candle]).ema25
            close = (df.iloc[candle]).Close 
            low = (df.iloc[candle]).Low 
            squeezedArea = (df.iloc[candle]).squeezedArea 
            squeezeCloseToEma = (df.iloc[candle]).squeezeCloseToEma 
            datetime = (df.iloc[candle]).datetime_est
            isUptrend = (df.iloc[candle]).isUptrend
            
            df2 = df.iloc[candle-window:candle]
            lastTreeOver = df2[df2['squeezeCloseToEma'] == EMA25['PRICE_ACCION_OVER_EMA'].value].tail(3).values

            current_date, current_price = self.get_date_price(candle)
            
            if self.position == POSITION['NEUTRAL'].value: 
                if len(lastTreeOver) == window and \
                    close>ema25 and \
                    squeezeCloseToEma and \
                    isUptrend:
                    
                    self.place_buy_order(candle, amount=self.amount)
                    self.position = POSITION['LONG'].value
                    buying_date, buying_price =  self.get_date_price(candle)
                    transaction = [datetime, 'long', candle, buying_price, 0, 0, 0]
                    
            elif self.position == POSITION['LONG'].value:

                #stop   = (close<ema25 or squeezedArea==EMA25['PRICE_ACCION_UNDER_EMA'].value)
                #stop = (current_price-buying_price) <= .50
                stop   = close<ema25
                target = (buying_price-current_price) >= 3
                
                if stop or target:
                    self.place_sell_order(candle, units=self.units)
                    self.position = POSITION['NEUTRAL'].value
                    current_date,  sell_price = self.get_date_price(candle)
                    transaction[4] = candle
                    transaction[5] = sell_price
                    transaction[6] = (sell_price/transaction[3]-1)*100
                    log.append(transaction)
                    
        self.close_out(candle)
        df2 = pd.DataFrame(log, columns=['datetime','direction','buy_index','buy','sell_index','sell','performance'])
        df2.to_csv('backtest.csv', index=False)
        
lobt = BacktestLongOnly('MSFT', '2022-09-01', '2024-09-21', 25000, verbose=False)
lobt.runStrategy()
