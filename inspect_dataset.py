import pandas as pd
from pathlib import Path
root = Path('c:/Users/adeha/Downloads/Final UI 2')
df = pd.read_csv(root / 'Credit-Risk-Poc-main' / 'demo_data' / 'clean_portfolio.csv')
print('shape', df.shape)
print('columns', df.columns.tolist())
print('target values', df['default'].value_counts(dropna=False).to_dict())
print('target dtype', df['default'].dtype)
print('head', df.head().to_dict(orient='list'))
