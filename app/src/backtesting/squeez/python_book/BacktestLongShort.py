from BacktestBase import *
import pandas as pd
import numpy as np
import pandas_ta as ta
from pandas_ta.volatility import kc 
import enum
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

class BacktestLongShort(BacktestBase):
    def __init__(self, symbol, start, end, amount, ftc=0.0, ptc=0.0, verbose=True):
        
        super().__init__(symbol, start, end, amount, ftc, ptc, verbose)

        df=self.data

        df['ema25_5min'] = BacktestLongShort.calculateEma(df,25)
        
        self.calculateBolingerAndKeltnerChannels(kc)
        self.detectSqueeze()
        self.detectSqueezeCloseToEMA()
        self.priceActionUptrendInShortTerm()
        
    def go_long(self, bar, units=None, amount=None):
        
        if self.position == POSITION['SHORT'].value:
            self.place_buy_order(bar, units=-self.units)
        if units:
            self.place_buy_order(bar, units=units)
        elif amount:
            if amount == 'all':
                amount = self.amount
            self.place_buy_order(bar, amount=amount)

    def go_short(self, bar, units=None, amount=None):
        
        if self.position == POSITION['LONG'].value:
            self.place_sell_order(bar, units=self.units)
        if units:
            self.place_sell_order(bar, units=units)
        elif amount:
            if amount == 'all':
                amount = self.amount
            self.place_sell_order(bar, amount=amount)

    def calculateEma(df, span):
        return df['close_5min'].ewm(span=span, adjust=False).mean()
        
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
        
        ''' Check if the pa is above the ema if it does then is true else check if there is a wigle room of .30 cents
        '''
        df['isPriceActionAboveEma25'] = np.where(df.ema25_5min > df.close5min_smooth, 
                                                     np.where((df.ema25_5min-df.close5min_smooth)<=zoneWidth, True, False), 
                                                 np.where(df.ema25_5min < df.close5min_smooth, True, False))
        
        ''' If in the count of the isPriceActionAboveEma25 (in the day YMD) there are False then return False
        '''
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
        stop = 'close5minSmooth<ema25_5min (long) or close5minSmooth>ema25_5min (short)'
        target = '(current_price-buying_price) >= 2 (long) or (selling_price-current_price) >= 2 (short)'
        
        msg = f'\n\nRunning squeeze strategy long and short'
        msg += f'\nSymbol:  {self.symbol} '
        msg += f'\nStop:   {stop} '
        msg += f'\nTarget: {target} '
        msg += f'\nFixed costs: {self.ftc} '
        msg += f'Proportional costs: {self.ptc}'
        print(msg)
        print('=' * 94)
        self.position = POSITION['NEUTRAL'].value
        self.trades = 0  # no trades yet
        self.amount = self.initial_amount  # reset initial capital
        window = 3
        log_sequence = []
        
        for candle in range(0, len(df)):

            ema25_5min = (df.iloc[candle]).ema25_5min
            squeezedArea = (df.iloc[candle]).squeezedArea 
            squeezeCloseToEma = (df.iloc[candle]).squeezeCloseToEma 
            datetime = (df.iloc[candle]).datetime_est
            date_est = (df.iloc[candle]).date_est
            time_est = (df.iloc[candle]).time_est
            isTheDayAbove25Ema = (df.iloc[candle]).isTheDayAbove25Ema 
            close5minSmooth = (df.iloc[candle]).close5min_smooth
            
            df_window = df.iloc[candle-window:candle]
            lastTreeOver = df_window[df_window['squeezeCloseToEma'] == EMA25['PRICE_ACCION_OVER_EMA'].value].tail(3).values
            lastTreeUnder = df_window[df_window['squeezeCloseToEma'] == EMA25['PRICE_ACCION_UNDER_EMA'].value].tail(3).values
            
            current_date, current_price = self.get_date_price(candle)
            initial_amount = self.amount
            
            if self.position == POSITION['NEUTRAL'].value:
                
                if len(lastTreeOver) == window and \
                    squeezeCloseToEma == EMA25['PRICE_ACCION_OVER_EMA'].value and \
                    isTheDayAbove25Ema == True:

                    self.go_long(candle, amount='all')
                    self.position = POSITION['LONG'].value

                    #LOG DATA
                    buying_date, buying_price =  self.get_date_price(candle)  
                    trans = [date_est, time_est, candle, self.symbol, self.units, round(buying_price,2), 'B']
                    log_sequence.append(trans)
    
                elif len(lastTreeUnder) == window and \
                    squeezeCloseToEma == EMA25['PRICE_ACCION_UNDER_EMA'].value and \
                    isTheDayAbove25Ema == False:

                    self.go_short(candle, amount='all')
                    self.position = POSITION['SHORT'].value

                    #LOG DATA
                    selling_date, selling_price =  self.get_date_price(candle)
                    trans = [date_est, time_est, candle, self.symbol, -self.units, round(selling_price,2), 'S']
                    log_sequence.append(trans)
 
            elif self.position == POSITION['LONG'].value:
                
                stop   = close5minSmooth<ema25_5min
                target = (current_price-buying_price) >= 2
                
                if stop or target:
                    units_before_transaction = self.units
                    self.place_sell_order(candle, units=self.units)
                    self.position = POSITION['NEUTRAL'].value

                    #LOG DATA
                    trans = [date_est, time_est, candle, self.symbol, units_before_transaction, round(current_price,2), 'S']
                    log_sequence.append(trans)
            
            elif self.position == POSITION['SHORT'].value:
                
                stop   = close5minSmooth>ema25_5min
                target = (selling_price-current_price) >= 2
                
                if stop or target:
                    units_before_transaction = -self.units
                    self.place_buy_order(candle, units=-self.units)
                    self.position = POSITION['NEUTRAL'].value

                    #LOG DATA
                    trans = [date_est, time_est, candle, self.symbol, units_before_transaction, round(current_price,2), 'B']
                    log_sequence.append(trans)
                    
        self.close_out(candle)

        df_log_sequence = pd.DataFrame(log_sequence, columns=['Date','Time','Candle','Symbol','Quantity','Price','Side'])
        #df_log_sequence.to_csv('trading_result.csv', index=False)
        conn = sq3.connect('trading_vow.sql') 
        df_log_sequence.to_sql('data', conn, if_exists='append')
        
        conn.close()

lobt = BacktestLongShort('AAPL', '2022-09-01', '2024-09-21', 10000, verbose=False, ftc=1)
lobt.runStrategy()
