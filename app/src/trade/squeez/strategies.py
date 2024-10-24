import pandas as pd
import numpy as np
import pandas_ta as ta
import enum
from pandas_ta.volatility import kc 

def squeez(df, window=1):

        # Bolinger Bands
        df.ta.bbands(append=True, length=20, std=2)
        
        # Initialize Keltner Channel Indictor
        kc=kc(high=df['high_5min'], low=df['low_5min'], close=df["close_5min"], window=20)
        
        #Bolinger Band Upper - Keltner Channel Upper
        df['bbu_minus_kcu'] = df['BBU_20_2.0'] - kc['KCUe_20_2']

        '''
        Determine if the price accion has been above the ema 25
        '''
        df['isPriceActionAboveEma25'] = np.where(df.ema25_5min > df.close5min_smooth, 
                                                    np.where((df.ema25_5min-df.close5min_smooth)<=zoneWidth, True, False), 
                                                 np.where(df.ema25_5min < df.close5min_smooth, True, False))
    
        df['isTheDayAbove25Ema'] = df.groupby('YMD').isPriceActionAboveEma25.transform(
            lambda x: False if x[x==False].value_counts().shape[0] > 0 else True)

    
        '''
        Detect if the squeeze is close to the ema 
        '''
    
        df['squeezeCloseToEma'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
    
        #Over the EMA
        cond =(
                (df.squeezedArea == EMA25['PRICE_ACCION_OVER_EMA'].value) &
                (
                    abs(df.low5min_smooth-df.ema25_5min<=zoneWidth)
                )
            )
        
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_OVER_EMA'].value
    
        #Under the EMA
        cond =(
            (
                df.squeezedArea == EMA25['PRICE_ACCION_UNDER_EMA'].value
            ) & 
            (
                abs(df.high5min_smooth-df.ema25_5min<=zoneWidth)
            )
        )
        
        df.loc[cond, 'squeezeCloseToEma'] = EMA25['PRICE_ACCION_UNDER_EMA'].value

        '''
        Detect if there is a squeeze
        '''
    
        df['squeezedArea'] = EMA25['PRICE_ACCION_NEUTRAL_EMA'].value
        cond = ((df.bbu_minus_kcu <= 0) & (df.close_5min < df.ema25_5min))
        df.loc[cond, 'squeezedArea'] = EMA25['PRICE_ACCION_UNDER_EMA'].value
        
        cond2 =((df.bbu_minus_kcu <= 0) & (df.close_5min > df.ema25_5min))
        df.loc[cond2, 'squeezedArea'] = EMA25['PRICE_ACCION_OVER_EMA'].value
    
    return df


