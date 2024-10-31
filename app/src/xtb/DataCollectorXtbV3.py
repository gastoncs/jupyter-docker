import pandas as pd
import numpy as np
import config
from datetime import datetime, timedelta,date
from xAPIConnector import *
from dateutil.relativedelta import *
from pathlib import Path 

user_id = config.user_id
pwd= config.pwd

class DataCollectorXtbV3():
    
    ''' Class for collection historical data from XTB using API 
    '''
    def __init__(self, symbol, start, end, period, cols_to_save=['Open', 'Close', 'High', 'Low'],
                 spread_col=False):
        
        self.symbol = symbol
        self.start = start
        self.end = end
        self.cols_to_save = cols_to_save
        self.data = None
        self.period_dict = {'1min': 1, '5min': 5, '15min': 15, '30min': 30, '1h': 60, '4h': 240, '1D': 1440}
        self.period = period
        self.spread_col=spread_col
        self.get_data()

    def __repr__(self):
        rep = "DataCollector(symbol = {}, start = {}, end = {}, period= {})"
        return rep.format(self.symbol, self.start, self.end, self.period)
    
    def history_converter(self, history):
        
        '''Convert data from dict to pandas df'''
    
        df_dict = history['returnData']['rateInfos']
        digits = history['returnData']['digits']

        df = pd.DataFrame.from_dict(df_dict)

        df['time'] = df['ctm'].apply(lambda x: datetime.fromtimestamp(x / 1000))
        df['Open'] = df['open'] / (10 ** digits)
        df['Close'] = df['Open'] + df['close'] / (10 ** digits)
        df['High'] = df['Open'] + df['high'] / (10 ** digits)
        df['Low'] = df['Open'] + df['low'] / (10 ** digits)

        df['bar']=df.index
        df.set_index("time", inplace=True, drop=False)
             
        df = df[self.cols_to_save]

        return df
        
    def get_data(self):
        
        ''' Collect and prepares the data'''
    
        filename=''
        end_date = datetime.strptime(self.end, '%Y-%m-%d')
        end = int(datetime.timestamp(end_date) * 1000)
        start_date = datetime.strptime(self.start, '%Y-%m-%d')
        start = int(datetime.timestamp(start_date) * 1000)
        args = {'info': {
            'end': end,
            'start': start,
            'symbol': self.symbol,
            'period': self.period_dict[self.period]
        }}
        client = APIClient()
        client.execute(loginCommand(user_id, pwd))
        history_data = client.commandExecute('getChartRangeRequest', arguments=args)
        df = self.history_converter(history_data)
        
        self.data = df
