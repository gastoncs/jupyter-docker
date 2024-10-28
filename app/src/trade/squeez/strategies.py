import pandas as pd
import numpy as np
import pandas_ta as ta
import enum
from pandas_ta.volatility import kc 
from scipy.signal import savgol_filter

position = 0
price = 0
comb = []

def squeez(df, window=1):

    df = df.copy()

    df = init(df)
    calculateBoolingerAndKeltnerChannels(df, kc)
    detectSqueeze(df)
    detectSqueezeCloseToEMA(df)
    isTheLastTreeSqueezeCloseToEmaOverOrUnderEma(df)
    priceActionUptrendInShortTerm(df)
    detectPosibleEntry(df)

    pos,buying_price = zip(* [setPosition(row[0],row[1],row[2],row[3]) 
                          for row in df[['close','close_smooth','ema25','posible_entry']].to_numpy()])
    df['position']=pos 
    df['price']=buying_price
                       
    df = df[['index','symbol','date_est','time_est','high','low','close','volume','open','close_smooth','ema25',
             'squeezed_area','squeeze_close_ema','posible_entry','qty','position','price']] 
    
    return df
    
def init(df):
    
    ''' Create columns if does not exist
    '''
    cols_to_check = ['high','low','close','volume','open','position']
    
    new_list =list(set(df.columns).union(cols_to_check))
    df = df.reindex(columns=sorted(new_list)).fillna(0)
    
    df['symbol'] = 'GOOGLE'
    df['qty'] = 10
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

def setPosition(close, close_smooth, ema, posible_entry):

    global position, price

    if posible_entry==POSITION['SHORT'].value:
        position=POSITION['SHORT'].value
        price = close
    elif posible_entry==POSITION['LONG'].value:
        position=POSITION['LONG'].value
        price = close
    else:
        if close_smooth>ema and position==POSITION['SHORT'].value or (price-close) >= 2:
            position=POSITION['NEUTRAL'].value
            price = 0
        elif close_smooth<ema and position==POSITION['LONG'].value or (close-price) >= 2:
            position=POSITION['NEUTRAL'].value
            price = 0

    return position,price
     
    
def detectPosibleEntry(df):

    df['posible_entry'] = POSITION['NEUTRAL'].value
    
    cond = (
        (df.squeeze_close_ema == EMA25['PRICE_ACCION_OVER_EMA'].value) & 
                (df.isTheDayAbove25Ema == True) & 
                        (df.lastTreeOver == True)
    )
    
    df.loc[cond, 'posible_entry'] = POSITION['LONG'].value

    cond2 = (
        (df.squeeze_close_ema == EMA25['PRICE_ACCION_UNDER_EMA'].value) & 
                (df.isTheDayAbove25Ema == False) & 
                        (df.lastTreeUnder == True)
    )
    
    df.loc[cond2, 'posible_entry'] = POSITION['SHORT'].value

def calculateBoolingerAndKeltnerChannels(df, kc):

    # Boolinger Bands
    df.ta.bbands(append=True, length=20, std=2)
    
    # Initialize Keltner Channel Indictor
    kc=kc(high=df['high'], low=df['low'], close=df["close"], window=20)
    
    #Boolinger Band Upper - Keltner Channel Upper
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
    
    df['squeeze_close_ema'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value

    ''' Over the EMA
    '''
    cond =(
            (
                df.squeezed_area == EMA25['PRICE_ACCION_OVER_EMA'].value
            ) &
            (
                abs(df.low_smooth-df.ema25<=zoneWidth)
            )
        )
    
    df.loc[cond, 'squeeze_close_ema'] = EMA25['PRICE_ACCION_OVER_EMA'].value

    ''' Under the EMA
    '''
    cond =(
        (
            df.squeezed_area == EMA25['PRICE_ACCION_UNDER_EMA'].value
        ) & 
        (
            abs(df.high_smooth-df.ema25<=zoneWidth)
        )
    )
    
    df.loc[cond, 'squeeze_close_ema'] = EMA25['PRICE_ACCION_UNDER_EMA'].value

def detectSqueeze(df):

    df['squeezed_area'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
    cond = ((df.bbu_minus_kcu <= 0) & (df.close < df.ema25))
    df.loc[cond, 'squeezed_area'] = EMA25['PRICE_ACCION_UNDER_EMA'].value
    
    cond2 =((df.bbu_minus_kcu <= 0) & (df.close > df.ema25))
    df.loc[cond2, 'squeezed_area'] = EMA25['PRICE_ACCION_OVER_EMA'].value

def isTheLastTreeSqueezeCloseToEmaOverOrUnderEma(df):

    df['lastTreeOver'] = df['squeeze_close_ema'].rolling(3).sum().eq(3)
    df['lastTreeUnder'] = df['squeeze_close_ema'].rolling(3).sum().eq(6)

class POSITION(enum.Enum):
    NEUTRAL = 0
    LONG = 1
    SHORT = -1
    
class EMA25(enum.Enum):
    PRICE_ACCION_NEUTRAL_EMA = 0
    PRICE_ACCION_OVER_EMA = 1
    PRICE_ACCION_UNDER_EMA = 2