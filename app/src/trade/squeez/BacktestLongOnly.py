import pandas as pd
import numpy as np
import pandas_ta as ta
import enum
from BacktestBase import *
from pandas_ta.volatility import kc 
import sqlite3 as sq3

class STACKED_EMA(enum.Enum):
    NEUTRAL = 0
    POSITIVE = 1
    NEGATIVE = 2
    
class POSITION(enum.Enum):
    NEUTRAL = 0
    LONG = 1
    SHORT = 2
    
class EMA25(enum.Enum):
    PRICE_ACCION_NEUTRAL_EMA = 0
    PRICE_ACCION_OVER_EMA = 1
    PRICE_ACCION_UNDER_EMA = 2

class BacktestLongOnly(BacktestBase):
    
    def __init__(self, symbol, start, end, amount, ftc=0.0, ptc=0.0, verbose=False):

        super().__init__(symbol, start, end, amount, ftc, ptc, verbose=False)

        df=self.data
        df2=self.data2

        df['ema25_5min'] = df['Close'].ewm(span=25, adjust=False).mean()
        self.dailyEmaStacked()

        self.merged_data(df,df2)
        
        self.calculateBolingerAndKeltnerChannels(kc)
        self.detectSqueeze()
        self.detectSqueezeCloseToEMA()
        self.priceActionUptrendInShortTerm()
                
    def calculateBolingerAndKeltnerChannels(self, kc)->None:
        
        df=self.data
        # Bolinger Bands
        df.ta.bbands(append=True, length=20, std=2)
        
        # Initialize Keltner Channel Indictor
        kc=kc(high=df['high_5min'], low=df['low_5min'], close=df["close_5min"], window=20)
        
        #Bolinger Band Upper - Keltner Channel Upper
        df['bbu_minus_kcu'] = df['BBU_20_2.0'] - kc['KCUe_20_2']
    
    def priceActionUptrendInShortTerm(self, zoneWidth = .30)->None:
        
        df=self.data
        df['isPriceActionAboveEma25'] = np.where(df.ema25_5min > df.close5min_smooth, 
                                                     np.where((df.ema25_5min-df.close5min_smooth)<=zoneWidth, True, False), 
                                                 np.where(df.ema25_5min < df.close5min_smooth, True, False))
    
        df['isTheDayAbove25Ema'] = df.groupby('YMD').isPriceActionAboveEma25.transform(
            lambda x: False if x[x==False].value_counts().shape[0] > 0 else True)
                
    def detectSqueezeCloseToEMA(self, zoneWidth = .30)->None:
        
        df=self.data

        df['squeezeCloseToEma'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
    
        ''' Over the EMA
        '''
        cond =(
                (df.squeezedArea == EMA25['PRICE_ACCION_OVER_EMA'].value) &
                (
                    abs(df.low5min_smooth-df.ema25_5min<=zoneWidth)
                )
            )
        
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_OVER_EMA'].value
    
        ''' Under the EMA
        '''
        cond =(
            (
                df.squeezedArea == EMA25['PRICE_ACCION_UNDER_EMA'].value
            ) & 
            (
                abs(df.high5min_smooth-df.ema25_5min<=zoneWidth)
            )
        )
        
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_UNDER_EMA'].value
    
    def detectSqueeze(self)->None:
        
        df=self.data
        df['squeezedArea'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
        cond = ((df.bbu_minus_kcu <= 0) & (df.close_5min < df.ema25_5min))
        df.loc[cond, 'squeezedArea'] = EMA25['PRICE_ACCION_UNDER_EMA'].value
        
        cond2 =((df.bbu_minus_kcu <= 0) & (df.close_5min > df.ema25_5min))
        df.loc[cond2, 'squeezedArea'] = EMA25['PRICE_ACCION_OVER_EMA'].value
                
    def runStrategy(self):
        
        ''' Backtesting Squeeze Strategy.
        '''
        df=self.data
        stop = 'close5minSmooth < ema25_5min'
        target = '(buying_price-current_price) >= 2'
        
        msg = f'\n\nRunning Squeeze strategy'
        msg += f'\nSymbol:  {self.symbol} '
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

            ema25_5min = (df.iloc[candle]).ema25_5min
            squeezedArea = (df.iloc[candle]).squeezedArea 
            squeezeCloseToEma = (df.iloc[candle]).squeezeCloseToEma 
            datetime = (df.iloc[candle]).datetime_est
            isTheDayAbove25Ema = (df.iloc[candle]).isTheDayAbove25Ema 
            areDailyEmaStacked = (df.iloc[candle]).areDailyEmaStacked
            close5minSmooth = (df.iloc[candle]).close5min_smooth
            
            window_df = df.iloc[candle-window:candle]
            lastTreeOver = window_df[window_df['squeezeCloseToEma'] == EMA25['PRICE_ACCION_OVER_EMA'].value].tail(3).values

            current_date, current_price = self.get_date_price(candle)

            initial_amount = self.amount
            if self.position == POSITION['NEUTRAL'].value: 
                if len(lastTreeOver) == window and \
                    squeezeCloseToEma == EMA25['PRICE_ACCION_OVER_EMA'].value and \
                    isTheDayAbove25Ema == True:
                    
                    self.place_buy_order(candle, amount=self.amount)
                    self.position = POSITION['LONG'].value
                    buying_date, buying_price =  self.get_date_price(candle)

                    entry_amount = buying_price * self.units
                    buying_price_formated = round(buying_price,2)
                    entry_amount_formated = round(entry_amount,2)
                    
                    transaction = [datetime, 'long', self.symbol ,candle, self.units, buying_price_formated, entry_amount_formated, 0, 0, 0, 0, 0, 0, 0]
                    
            elif self.position == POSITION['LONG'].value:

                stop   = close5minSmooth<ema25_5min
                target = (buying_price-current_price) >= 2
                
                if stop or target:
                    
                    units_before_sell = self.units
                    self.place_sell_order(candle, units=self.units)
                    self.position = POSITION['NEUTRAL'].value
                    current_date,  sell_price = self.get_date_price(candle)

                    exit_amount = sell_price * units_before_sell
                    
                    sell_price_formated = round(sell_price,2)
                    exit_amount_formated =  round(sell_price * units_before_sell,2)
                    performance =  round((exit_amount/entry_amount-1)*100,2)
                    move =  round(sell_price-buying_price,2)
                    balance =  round(self.amount,2)
                    gain_or_loss =  round(exit_amount - entry_amount,2)
                
                    transaction[7] = candle
                    transaction[8] = sell_price_formated
                    transaction[9] = exit_amount_formated
                    transaction[10] = gain_or_loss
                    transaction[11] = performance
                    transaction[12] = move
                    transaction[13] = balance
    
                    log.append(transaction)
                    
        self.close_out(candle)
        
        df_log = pd.DataFrame(log, columns=['datetime','direction','symbol','buy_index', 'units', 
                                                'buying_price', 'entry_amount','sell_index','sell_price','exit_amount',
                                                'gain_or_loss', 'performance','move', 'balance'])

        conn = sq3.connect('long_backtest_data.sql') 
        df_log.to_sql('data', conn, if_exists='append')
        conn.close()

lobt = BacktestLongOnly('IWM', '2022-09-01', '2024-09-21', 10000, verbose=False)
lobt.runStrategy()