import pandas as pd
import numpy as np
import pandas_ta as ta
import enum
from pandas_ta.volatility import kc 
from scipy.signal import savgol_filter

def squeez(df, window=1):

    df = df.copy()
    
    df['ema25'] = df['close'].ewm(span=25, adjust=False).mean()
    df["close_smooth"] = savgol_filter(df.close, 49, 5)
    df["high_smooth"] = savgol_filter(df.high, 49, 5)
    df["low_smooth"] = savgol_filter(df.low, 49, 5)
    df['YMD'] = df.index.strftime('%Y%m%d')
    df["est"] = pd.to_datetime(df.index, unit='ms').tz_localize('UTC').tz_convert('US/Eastern')
    df.set_index("YMD")

    calculateBolingerAndKeltnerChannels(df, kc)
    detectSqueeze(df)
    detectSqueezeCloseToEMA(df)
    priceActionUptrendInShortTerm(df)

    ''' GO LONG
    '''
    cond = (
                (df['position'] == POSITION['NEUTRAL'].value) || (("position" in df.columns)==False)
           ) & 
           (
             (df.squeezeCloseToEma == EMA25['PRICE_ACCION_OVER_EMA'].value) & (df.isTheDayAbove25Ema == True)
           )

    df.loc[cond, 'buying_price'] = df['close']
    df.loc[cond, 'position'] = POSITION['LONG'].value
    
    ''' IF WE ARE LONG GET OUT IF WE HIT OUR TARGET OR STOP
    '''
    cond2 = (
                df['position'] == POSITION['LONG'].value
            ) & 
            (
                (df.close5minSmooth<df.ema25) || ((df['close']-df['buying_price'].tail(1)) >= 2)
            )
    
    df.loc[cond2, 'position'] = POSITION['NEUTRAL'].value

    ''' GO SHORT
    '''
    cond3 = (
                (df['position'] == POSITION['NEUTRAL'].value) || (("position" in df.columns)==False)
            ) & 
            (
                (df.squeezeCloseToEma == EMA25['PRICE_ACCION_UNDER_EMA'].value) & (df.isTheDayAbove25Ema == False)
            )

    df.loc[cond3, 'selling_price'] = df['close']
    df.loc[cond3, 'position'] = POSITION['SHORT'].value

    ''' IF WE ARE SHORT GET OUT IF WE HIT OUR TARGET OR STOP
    '''
    cond4 = (
                df['position'] == POSITION['SHORT'].value
            ) & 
            (
                (df.close5minSmooth>df.ema25) || ((df['selling_price'].tail(1)-df['close']) >= 2)
            )
    
    df.loc[cond4, 'position'] = POSITION['NEUTRAL'].value
    
    '''
    if self.position == POSITION['NEUTRAL'].value:
        
        if len(lastTreeOver) == window and \
            squeezeCloseToEma == EMA25['PRICE_ACCION_OVER_EMA'].value and \
            isTheDayAbove25Ema == True:

            self.go_long(candle, amount='all')
            self.position = POSITION['LONG'].value

            #LOG DATA
            #buying_date, buying_price =  self.get_date_price(candle)  
            #trans = [date_est, time_est, candle, self.symbol, self.units, round(buying_price,2), 'B']
            #log_sequence.append(trans)

        elif len(lastTreeUnder) == window and \
            squeezeCloseToEma == EMA25['PRICE_ACCION_UNDER_EMA'].value and \
            isTheDayAbove25Ema == False:

            self.go_short(candle, amount='all')
            self.position = POSITION['SHORT'].value

            #LOG DATA
            #selling_date, selling_price =  self.get_date_price(candle)
            #trans = [date_est, time_est, candle, self.symbol, -self.units, round(selling_price,2), 'S']
            #log_sequence.append(trans)

    elif self.position == POSITION['LONG'].value:
        
        stop   = close5minSmooth<ema25
        target = (current_price-buying_price) >= 2
        
        if stop or target:
            units_before_transaction = self.units
            self.place_sell_order(candle, units=self.units)
            self.position = POSITION['NEUTRAL'].value

            #LOG DATA
            #trans = [date_est, time_est, candle, self.symbol, units_before_transaction, round(current_price,2), 'S']
            #log_sequence.append(trans)
    
    elif self.position == POSITION['SHORT'].value:
        
        stop   = close5minSmooth>ema25
        target = (selling_price-current_price) >= 2
        
        if stop or target:
            units_before_transaction = -self.units
            self.place_buy_order(candle, units=-self.units)
            self.position = POSITION['NEUTRAL'].value

            #LOG DATA
            #trans = [date_est, time_est, candle, self.symbol, units_before_transaction, round(current_price,2), 'B']
            #log_sequence.append(trans)

    '''
    
    return df

def calculateBolingerAndKeltnerChannels(df, kc):

    # Bolinger Bands
    df.ta.bbands(append=True, length=20, std=2)
    
    # Initialize Keltner Channel Indictor
    kc=kc(high=df['high'], low=df['low'], close=df["close"], window=20)
    
    #Bolinger Band Upper - Keltner Channel Upper
    df['bbu_minus_kcu'] = df['BBU_20_2.0'] - kc['KCUe_20_2']
    
def priceActionUptrendInShortTerm(df, zoneWidth = .30):

    ''' Check if the pa is above the ema if it does then is true else check if there is a wigle room of .30 cents
    '''
    df['isPriceActionAboveEma25'] = np.where(df.ema25 > df.close_smooth, 
                                                 np.where((df.ema25-df.close_smooth)<=zoneWidth, True, False), 
                                             np.where(df.ema25 < df.close_smooth, True, False))
    
    ''' If in the count of the isPriceActionAboveEma25 (in the day YMD) there are False then return False
    '''
    df['isTheDayAbove25Ema'] = df.groupby('YMD').isPriceActionAboveEma25.transform(
        lambda x: False if x[x==False].value_counts().shape[0] > 0 else True)

def detectSqueezeCloseToEMA(df, zoneWidth = .30)->None:
    
    df['squeezeCloseToEma'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value

    ''' Over the EMA
    '''
    cond =(
            (df.squeezedArea == EMA25['PRICE_ACCION_OVER_EMA'].value) &
            (
                abs(df.low_smooth-df.ema25<=zoneWidth)
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
            abs(df.high_smooth-df.ema25<=zoneWidth)
        )
    )
    
    df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_UNDER_EMA'].value

def detectSqueeze(df):

    df['squeezedArea'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
    cond = ((df.bbu_minus_kcu <= 0) & (df.close < df.ema25))
    df.loc[cond, 'squeezedArea'] = EMA25['PRICE_ACCION_UNDER_EMA'].value
    
    cond2 =((df.bbu_minus_kcu <= 0) & (df.close > df.ema25))
    df.loc[cond2, 'squeezedArea'] = EMA25['PRICE_ACCION_OVER_EMA'].value
    
class POSITION(enum.Enum):
    NEUTRAL = 0
    LONG = 1
    SHORT = -1
    
class EMA25(enum.Enum):
    PRICE_ACCION_NEUTRAL_EMA = 0
    PRICE_ACCION_OVER_EMA = 1
    PRICE_ACCION_UNDER_EMA = 2