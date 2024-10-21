import pandas as pd
import numpy as np
import pandas_ta as ta
import enum
import math
from BacktestBase import *
from pandas_ta.volatility import kc 

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
    def __init__(self, symbol, start, end, amount, ftc=0.0, ptc=0.0, verbose=True):

        super().__init__(symbol, start, end, amount, ftc, ptc, verbose=True)

        df=self.data
        df2=self.data2

        df['ema25_5min'] = BacktestLongOnly.calculateEma(df,25)
        self.dailyEmaStacked()

        self.merged_data(df,df2)
        
        self.calculateBolingerAndKeltnerChannels(kc)
        self.detectSqueeze()
        self.detectSqueezeCloseToEMA()
        self.priceActionUptrendInShortTerm()

    def calculateEma(df, span):
        
        return df['Close'].ewm(span=span, adjust=False).mean()
                
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
        
    def dailyEmaStacked(self)->None:
        
        df2=self.data2
        df2['ema89'] = BacktestLongOnly.calculateEma(df2,89)
        df2['ema55'] = BacktestLongOnly.calculateEma(df2,55)
        df2['ema34'] = BacktestLongOnly.calculateEma(df2,34)
        df2['ema21'] = BacktestLongOnly.calculateEma(df2,21)
        df2['ema8'] = BacktestLongOnly.calculateEma(df2,8)
    
        SP = ((df2.ema8 > df2.ema21) & \
              (df2.ema21 > df2.ema34) & \
              (df2.ema34 > df2.ema55) & \
              (df2.ema55 > df2.ema89))
        
        df2.loc[SP, 'areDailyEmaStacked'] = STACKED_EMA['POSITIVE'].value
        
        SN = ((df2.ema8 < df2.ema21) & \
              (df2.ema21 < df2.ema34) & \
              (df2.ema34 < df2.ema55) & \
              (df2.ema55 < df2.ema89))
        
        df2.loc[SN, 'areDailyEmaStacked'] = STACKED_EMA['NEGATIVE'].value    
        df2.loc[((SP==False) & (SN==False)), 'areDailyEmaStacked'] = STACKED_EMA['NEUTRAL'].value
                
    def runStrategy(self):
        ''' Backtesting Squeeze Strategy.
        '''
        df=self.data
        stop = 'close<ema25_5min'
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

            ema25_5min = (df.iloc[candle]).ema25_5min
            close = (df.iloc[candle]).close_5min 
            low = (df.iloc[candle]).low_5min 
            squeezedArea = (df.iloc[candle]).squeezedArea 
            squeezeCloseToEma = (df.iloc[candle]).squeezeCloseToEma 
            datetime = (df.iloc[candle]).datetime_est
            isTheDayAbove25Ema = (df.iloc[candle]).isTheDayAbove25Ema 
            areDailyEmaStacked = (df.iloc[candle]).areDailyEmaStacked
            close5minSmooth = (df.iloc[candle]).close5min_smooth
            
            df2 = df.iloc[candle-window:candle]
            lastTreeOver = df2[df2['squeezeCloseToEma'] == EMA25['PRICE_ACCION_OVER_EMA'].value].tail(3).values

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
                    transaction = [datetime, 'long', candle, format(self.units, '.2f'), format(buying_price, '.2f'), format(entry_amount, '.2f'), 0, 0, 0, 0, 0, 0]
                    
            elif self.position == POSITION['LONG'].value:

                #stop   = (close5minSmooth<ema25_5min or squeezedArea==EMA25['PRICE_ACCION_UNDER_EMA'].value) NOO!! 2.94
                #stop   = (squeezedArea==EMA25['PRICE_ACCION_UNDER_EMA'].value) NO!!
                #stop = (current_price-buying_price) <= -1 
                stop   = close5minSmooth<ema25_5min
                target = (buying_price-current_price) >= 3 
                
                if stop or target:
                    units_before_sell = self.units
                    self.place_sell_order(candle, units=self.units)
                    self.position = POSITION['NEUTRAL'].value
                    current_date,  sell_price = self.get_date_price(candle)

                    exit_amount = sell_price * units_before_sell
                    
                    transaction[6] = candle
                    transaction[7] = format(sell_price, '.2f')
                    transaction[8] = format(sell_price * units_before_sell, '.2f')
                    transaction[9] = format((exit_amount/entry_amount-1)*100, '.2f')
                    transaction[10] = format(sell_price-buying_price, '.2f')
                    transaction[11] = format(self.amount, '.2f')
    
                    log.append(transaction)
                    
        self.close_out(candle)
        df_log = pd.DataFrame(log, columns=['datetime','direction','buy_index', 'units', 'buying_price', 'entry_amount','sell_index','sell_price','exit_amount','performance','move', 'balance'])
        df_log.to_csv('backtest.csv', index=False)
        
lobt = BacktestLongOnly('MSFT', '2022-09-01', '2024-09-21', 25000, verbose=False)
lobt.runStrategy()
