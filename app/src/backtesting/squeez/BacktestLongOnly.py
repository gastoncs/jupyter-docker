from BacktestBase import *
import pandas as pd
import numpy as np
import pandas_ta as ta
from pandas_ta.volatility import kc 
import enum

class POSITION(enum.Enum):
    NEUTRAL = 0
    LONG = 1
    SHORT = 2
    
class EMA25(enum.Enum):
    PRICE_ACCION_NEUTRAL = 0
    PRICE_ACCION_UNDER = 1
    PRICE_ACCION_OVER = 2

class BacktestLongOnly(BacktestBase):
    def __init__(self, symbol, start, end, amount, ftc=0.0, ptc=0.0, verbose=True):

        super().__init__(symbol, start, end, amount, ftc, ptc, verbose)
        
        self.calculateEMA25()
        self.calculateBolingerAndKeltnerChannels(kc)
        self.detectSqueeze()
        self.detectSqueezeCloseToEMA()

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

    def detectSqueezeCloseToEMA(self, zoneWidth = .30)->None:
        df=self.data
        df['squeezeCloseToEma'] = EMA25['PRICE_ACCION_NEUTRAL'].value
        
        cond =((df.squeezedArea == EMA25['PRICE_ACCION_OVER'].value) & (abs(df.Low-df.ema25)<=zoneWidth))
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_OVER'].value
    
        cond =((df.squeezedArea == EMA25['PRICE_ACCION_UNDER'].value) & (abs(df.High-df.ema25)<=zoneWidth))
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_UNDER'].value
    
    def detectSqueeze(self)->None:
        df=self.data
        df['squeezedArea'] = EMA25['PRICE_ACCION_NEUTRAL'].value
        cond = ((df.bbu_minus_kcu <= 0) & (df.Close < df.ema25))
        df.loc[cond, 'squeezedArea'] = EMA25['PRICE_ACCION_UNDER'].value
        
        cond2 =((df.bbu_minus_kcu <= 0) & (df.Close > df.ema25))
        df.loc[cond2, 'squeezedArea'] = EMA25['PRICE_ACCION_OVER'].value
    
    def runStrategy(self):
        ''' Backtesting Squeeze Strategy.
        '''
        df=self.data
        msg = f'\n\nRunning Squeeze strategy'
        msg += f'\nfixed costs {self.ftc} '
        msg += f'proportional costs {self.ptc}'
        print(msg)
        print('=' * 55)
        self.position = POSITION['NEUTRAL'].value
        self.trades = 0  # no trades yet
        self.amount = self.initial_amount  # reset initial capital
        window = 3

        for candle in range(0, len(df)):

            ema25 = (df.iloc[candle]).ema25
            close = (df.iloc[candle]).Close 
            squeezeCloseToEma = (df.iloc[candle]).squeezeCloseToEma 

            df2 = df.iloc[candle-window:candle]
            lastTreeOver = df2[df2['squeezeCloseToEma'] == EMA25['PRICE_ACCION_OVER'].value].tail(3).values
            
            if self.position == POSITION['NEUTRAL'].value: 
                if len(lastTreeOver) == window and close>ema25 and squeezeCloseToEma: 
                    self.place_buy_order(candle, amount=self.amount)
                    self.position = POSITION['LONG'].value
            elif self.position == POSITION['LONG'].value:
                if self.data['squeezeCloseToEma'].iloc[candle] == EMA25['PRICE_ACCION_OVER'].value:
                    self.place_sell_order(candle, units=self.units)
                    self.position = POSITION['NEUTRAL'].value
                    
        self.close_out(candle)
    
lobt = BacktestLongOnly('MSFT', '2022-09-01', '2024-09-21', 25000, verbose=False)
lobt.runStrategy()
