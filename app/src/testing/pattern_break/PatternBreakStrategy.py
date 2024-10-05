import numpy as np
import pandas as pd
from pylab import mpl, plt
import plotly.express as px
from datetime import datetime

plt.style.use('seaborn-v0_8')
mpl.rcParams['font.family'] = 'serif'

class PatternBreakStrategy(object):

    def __init__(self, data):
        self.meta = data
        self.data = data.data
        
    def check_for_long_market(self):
        
        return np.where(self.data['price_daily'].mean() > self.data['sma_50_daily'].mean(), 1, 0)
        
    def plot_data(self):
        
        ''' 
        Plots the cumulative performance of the trading strategy
        compared to the symbol.
        '''
        
        if self.data is None:
            print('No results to plot yet. Run a strategy.')

        title = self.meta.symbol+'\n From:'+self.meta.start+' To:'+self.meta.end

        data = pd.DataFrame(self.data,
                            columns=['datetime','price_5min','ema_25_5min','ema_20_daily','sma_50_daily','ema_20_hourly'])

        fig = px.line(data, x="datetime", 
                      y=['price_5min', 'ema_25_5min','ema_20_daily','sma_50_daily','ema_20_hourly'], title=title,
                     width=1000, height=600)
        fig.show()
