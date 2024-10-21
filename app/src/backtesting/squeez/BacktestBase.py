#
# Python Script with Base Class
# for Event-Based Backtesting
#
# Python for Algorithmic Trading
# (c) Dr. Yves J. Hilpisch
# The Python Quants GmbH
#
import numpy as np
import pandas as pd
from pylab import mpl, plt
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from scipy.signal import savgol_filter

plt.style.use('seaborn-v0_8')
mpl.rcParams['font.family'] = 'serif'

class BacktestBase(object):
    ''' Base class for event-based backtesting of trading strategies.

    Attributes
    ==========
    symbol: str
        TR RIC (financial instrument) to be used
    start: str
        start date for data selection
    end: str
        end date for data selection
    amount: float
        amount to be invested either once or per trade
    ftc: float
        fixed transaction costs per trade (buy or sell)
    ptc: float
        proportional transaction costs per trade (buy or sell)

    Methods
    =======
    get_data:
        retrieves and prepares the base data set
    plot_data:
        plots the closing price for the symbol
    get_date_price:
        returns the date and price for the given bar
    print_balance:
        prints out the current (cash) balance
    print_net_wealth:
        prints out the current net wealth
    place_buy_order:
        places a buy order
    place_sell_order:
        places a sell order
    close_out:
        closes out a long or short position
    '''

    def __init__(self, symbol, start, end, amount,
                 ftc=0.0, ptc=0.0, verbose=True):
        self.symbol = symbol
        self.start = start
        self.end = end
        self.initial_amount = amount
        self.amount = amount
        self.ftc = ftc
        self.ptc = ptc
        self.units = 0
        self.position = 0
        self.trades = 0
        self.perf = 0
        self.verbose = verbose
        self.get_data()

    def get_data(self):
        ''' Retrieves and prepares the data.
        '''
        if self.symbol == 'SPY':
            df = pd.read_csv("../data/SPY/SPY.USUSD_Candlestick_5_M_ASK_05.10.2022-05.10.2024.csv")
            df2 = pd.read_csv("../data/SPY/SPY.USUSD_Candlestick_1_D_ASK_05.10.2022-05.10.2024.csv")
        elif self.symbol == 'TSLA':
            df = pd.read_csv("../data/TSLA/TSLA.USUSD_Candlestick_5_M_ASK_05.10.2022-05.10.2024.csv")
            df2 = pd.read_csv("../data/TSLA/TSLA.USUSD_Candlestick_1_D_ASK_05.10.2022-05.10.2024.csv")
        
        df2.reset_index(drop=True, inplace=True)
        
        df['Gmt time']=df["Gmt time"].str.replace(".000","")
        df['Gmt time']=pd.to_datetime(df['Gmt time'],format='%d.%m.%Y %H:%M:%S')
        
        df2['Gmt time']=df2["Gmt time"].str.replace(".000","")
        df2['Gmt time']=pd.to_datetime(df2['Gmt time'],format='%d.%m.%Y %H:%M:%S')
        
        df['YMD'] = df['Gmt time'].dt.strftime('%Y%m%d')
        df2['YMD'] = df2['Gmt time'].dt.strftime('%Y%m%d')
    
        df.set_index("YMD")
        df2.set_index("YMD")
        
        self.data = df.dropna()
        self.data2 = df2.dropna()
        
    def merged_data(self, df, df2):
    
        df = pd.merge(df, df2, how="right", on=["YMD"])
        
        df.rename(columns={"Open_x": "open_5min"}, inplace=True)
        df.rename(columns={"High_x": "high_5min"}, inplace=True)
        df.rename(columns={"Low_x": "low_5min"}, inplace=True)
        df.rename(columns={"Volume_x": "volume_5min"}, inplace=True)
        df.rename(columns={"Close_x": "close_5min"}, inplace=True)
        df.rename(columns={"Close_y": "close_daily"}, inplace=True)
        df.rename(columns={'Gmt time_x':'datetime_gmt'}, inplace = True)
        
        df['datetime_est']=pd.to_datetime(df["datetime_gmt"], unit='ms').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df["close5min_smooth"] = savgol_filter(df.close_5min, 49, 5)
        df["high5min_smooth"] = savgol_filter(df.high_5min, 49, 5)
        df["low5min_smooth"] = savgol_filter(df.low_5min, 49, 5)
    
        df['price'] = df['close_5min']

        fromTodayStart = '2022-10-05 09:30:00'
        toNow   = '2024-10-05 16:00:00'
        df = df[df['datetime_est'].between(fromTodayStart, toNow)]
        
        df = df[df.notnull().all(axis=1)]
        df=df[(df.volume_5min != 0)]
        df=df[df.high_5min!=df.low_5min]
    
        df.reset_index(drop=True, inplace=True)

        self.data = df
    
    def plot_data(self, cols=None):
        ''' Plots the closing prices for symbol.
        '''
        if cols is None:
            cols = ['price']
        self.data[cols].plot(figsize=(10, 6), title=self.symbol)

    def get_date_price(self, bar):
        ''' Return date and price for bar.
        '''
        date = str(self.data.index[bar])[:10]
        price = self.data.price.iloc[bar]
        return date, price

    def print_balance(self, bar):
        ''' Print out current cash balance info.
        '''
        date, price = self.get_date_price(bar)
        print(f'{date} | current balance {self.amount:.2f}')
        
    def net_wealth(self, bar):
        ''' Current cash balance info.
        '''
        date, price = self.get_date_price(bar)
        return self.units * price + self.amount
        
    def print_net_wealth(self, bar):
        ''' Print out current cash balance info.
        '''
        date, price = self.get_date_price(bar)
        net_wealth = self.units * price + self.amount
        print(f'{date} | current net wealth {net_wealth:.2f}')

    def place_buy_order(self, bar, units=None, amount=None):
        ''' Place a buy order.
        '''
        date, price = self.get_date_price(bar)
        if units is None:
            units = int(amount / price)
        self.amount -= (units * price) * (1 + self.ptc) + self.ftc
        self.units += units
        self.trades += 1
        if self.verbose:
            print(f'{date} | buying {units} units at {price:.2f}')
            self.print_balance(bar)
            self.print_net_wealth(bar)

    def place_sell_order(self, bar, units=None, amount=None):
        ''' Place a sell order.
        '''
        date, price = self.get_date_price(bar)
        if units is None:
            units = int(amount / price)
        self.amount += (units * price) * (1 - self.ptc) - self.ftc
        self.units -= units
        self.trades += 1
        if self.verbose:
            print(f'{date} | selling {units} units at {price:.2f}')
            self.print_balance(bar)
            self.print_net_wealth(bar)

    def close_out(self, bar):
        ''' Closing out a long or short position.
        '''
        date, price = self.get_date_price(bar)
        self.amount += self.units * price
        self.units = 0
        self.trades += 1
        if self.verbose:
            print(f'{date} | inventory {self.units} units at {price:.2f}')
            print('=' * 55)
        print('Final balance   [$] {:.2f}'.format(self.amount))
        self.perf = ((self.amount - self.initial_amount) /
                self.initial_amount * 100)
        print('Net Performance [%] {:.2f}'.format(self.perf))
        print('Trades Executed [#] {}'.format(self.trades))
        print('=' * 55)
