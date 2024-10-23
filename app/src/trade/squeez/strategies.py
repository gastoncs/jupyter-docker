import pandas as pd
import numpy as np


def contrarian(df, window=1):
    df["returns"] = np.log(df['close'] / df['close'].shift(1))
    df["position"] = -np.sign(df["returns"].rolling(window).mean())
    return df


