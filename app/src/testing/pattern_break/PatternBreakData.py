import numpy as np
import pandas as pd

class PatternBreakData(object):

    def __init__(self, symbol, start, end, dataCollector, refreshData):
        
        self.symbol = symbol
        self.start = start
        self.end = end
        self.results = None
        self.dataCollector = dataCollector
        self.refreshData = refreshData
        self.getData()
        
    def get_data(self):
        
        ''' Retrieves and prepares the data.
        '''
        if(self.refreshData):

            ''' Get daily data
            '''
            daily=self.dataCollector(symbol=self.symbol, start=self.start, end=self.end, period='1D',
                            spread_col=False, cols_to_save=['YMD','Close'])

            daily.data['ema_20_daily'] = daily.data['Close'].ewm(span=20, adjust=False).mean()
            daily.data['sma_50_daily'] = daily.data['Close'].rolling(50).mean()
            
            daily.data.rename(columns={"Close": "price_daily"}, inplace=True)

            ''' Get 1 hour data
            '''
            hourly=self.dataCollector(symbol=self.symbol, start=self.start, end=self.end, period='1h',
                            spread_col=False, cols_to_save=['YMDH','Close'])

            hourly.data['ema_20_hourly'] = hourly.data['Close'].ewm(span=20, adjust=False).mean()
            
            hourly.data.rename(columns={"Close": "price_hourly"}, inplace=True)

            ''' Get 5 minutes data
            '''
            fivemin=self.dataCollector(symbol=self.symbol, start=self.start, end=self.end, period='5min',
                            spread_col=False, cols_to_save=['YMDH','YMD','Date','Close'])

            fivemin.data['ema_25_5min'] = fivemin.data['Close'].ewm(span=25, adjust=False).mean()
            
            fivemin.data.rename(columns={"Close": "price_5min"}, inplace=True)
            fivemin.data.rename(columns={"Date": "datetime"}, inplace=True)
            
            ''' Merge the 3 data collections
            '''
            ymdh = pd.merge(fivemin.data, hourly.data, how="right", on=["YMDH"])
            result = pd.merge(ymdh, daily.data, how="right", on=["YMD"])

            result.dropna(subset=['datetime'], how='all', inplace=True)
            result.drop(['YMD'],axis=1, inplace=True)
            result.drop(['YMDH'],axis=1, inplace=True)
            
            store=pd.HDFStore("data/patternBreakData.h5", "w")  
            store.put("data", result, format="table")  
        else:
            store=pd.HDFStore("data/patternBreakData.h5", "r")  

        data = store.select('/data')
        data.notnull().all(axis=1)
        store.close() 

        data['return'] = np.log(data['price_5min'] / data['price_5min'].shift(1))
        self.data = data