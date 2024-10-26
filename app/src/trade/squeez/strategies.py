import pandas as pd
import numpy as np
import pandas_ta as ta
import enum
from pandas_ta.volatility import kc 
from scipy.signal import savgol_filter

def squeez(df, window=1):

    df = df.copy()

    df = init(df)
    calculateBolingerAndKeltnerChannels(df, kc)
    detectSqueeze(df)
    detectSqueezeCloseToEMA(df)
    isTheLastTreeSqueezeCloseToEmaOverOrUnderEma(df)
    priceActionUptrendInShortTerm(df)
    detectPosition(df)

    df = df[['index','date_est','time_est','high','low','close','volume','open','position','buying_price',
             'selling_price','lastTreeOver','lastTreeUnder']] 
    
    return df
    
def init(df):
    
    ''' Create columns if does not exist
    '''
    cols_to_check = ['index','high','low','close','volume','open','position']
    new_list =list(set(df.columns).union(cols_to_check))
    df = df.reindex(columns=sorted(new_list)).fillna(0)
    
    df['ema25'] = df['close'].ewm(span=25, adjust=False).mean()
    df["close_smooth"] = savgol_filter(df.close, 49, 5)
    df["high_smooth"] = savgol_filter(df.high, 49, 5)
    df["low_smooth"] = savgol_filter(df.low, 49, 5)
    df['YMD'] = df.index.strftime('%Y%m%d')
    estTime = pd.to_datetime(df.index, unit='ms').tz_localize('UTC').tz_convert('US/Eastern')
    df["est"] = estTime.strftime('%Y-%m-%d %H:%M:%S')
    df['date_est']=estTime.date
    df['time_est']=estTime.time

    df.set_index("YMD")

    return df
    
def detectPosition(df):
    
    ''' START POSITION
    '''
    
    ''' GO LONG
    '''
    cond = (
                (
                   (df['position'] == POSITION['NEUTRAL'].value) & (df['lastTreeOver']==3)
                ) & 
                (
                    (df.squeezeCloseToEma == EMA25['PRICE_ACCION_OVER_EMA'].value) & (df.isTheDayAbove25Ema == True)
                )
            )

    df.loc[cond, 'buying_price'] = df['close']
    df.loc[cond, 'position'] = POSITION['LONG'].value
    
    ''' GO SHORT
    '''
    cond2 = (
                (
                    (df['position'] == POSITION['NEUTRAL'].value) & (df['lastTreeUnder']==3)
                ) & 
                (
                    (df.squeezeCloseToEma == EMA25['PRICE_ACCION_UNDER_EMA'].value) & (df.isTheDayAbove25Ema == False)
                )
            )

    df.loc[cond2, 'selling_price'] = df['close']
    df.loc[cond2, 'position'] = POSITION['SHORT'].value

    
    ''' TARGET AND STOPS
    '''
    
    ''' GET OUT IF WE HIT OUR TARGET OR STOP IN THE LONG POSITION
    '''
    cond3 = (
                (
                    df['position'] == POSITION['LONG'].value
                ) & 
                (
                    (df.close_smooth<df.ema25) | ((df['close']-df['buying_price'].tail(1)) >= 2)
                )
            )
    
    df.loc[cond3, 'position'] = POSITION['NEUTRAL'].value
    
    ''' GET OUT IF WE HIT OUR TARGET OR STOP IN THE SHORT POSITION
    '''
    cond4 = (
                (
                    df['position'] == POSITION['SHORT'].value
                ) & 
                (
                    (df.close_smooth>df.ema25) | ((df['selling_price'].tail(1)-df['close']) >= 2)
                )
            )
    
    df.loc[cond4, 'position'] = POSITION['NEUTRAL'].value
    
    df = df[['index', 'est', 'high','low','close','volume','open','position','buying_price','selling_price','lastTreeOver','lastTreeUnder']]   

def calculateBolingerAndKeltnerChannels(df, kc):

    # Bolinger Bands
    df.ta.bbands(append=True, length=20, std=2)
    
    # Initialize Keltner Channel Indictor
    kc=kc(high=df['high'], low=df['low'], close=df["close"], window=20)
    
    #Bolinger Band Upper - Keltner Channel Upper
    df['bbu_minus_kcu'] = df['BBU_20_2.0'] - kc['KCUe_20_2']
    
def priceActionUptrendInShortTerm(df, zoneWidth = .30):

    ''' Check if the price action is above the ema if it does then is true else check if there is a wigle room of .30 cents
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
            (
                df.squeezedArea == EMA25['PRICE_ACCION_OVER_EMA'].value
            ) &
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

def isTheLastTreeSqueezeCloseToEmaOverOrUnderEma(df):
    
    df['lastTreeOver'] = df['squeezeCloseToEma'].tail(3).apply(lambda x: x==EMA25['PRICE_ACCION_OVER_EMA'].value).count()
    df['lastTreeUnder'] = df['squeezeCloseToEma'].tail(3).apply(lambda x: x==EMA25['PRICE_ACCION_UNDER_EMA'].value).count()


class POSITION(enum.Enum):
    NEUTRAL = 0
    LONG = 1
    SHORT = -1
    
class EMA25(enum.Enum):
    PRICE_ACCION_NEUTRAL_EMA = 0
    PRICE_ACCION_OVER_EMA = 1
    PRICE_ACCION_UNDER_EMA = 2