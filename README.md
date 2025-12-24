# summary:
This repository contains a series of uv modules that each be packaged to a python aws lambda that gets executed periodically.

This repository contains a 1 command deployment of the full stack via terraform.

# modules:
1. python aws lambda that uses yahoo finance to download daily stock data using a config file containing a list of stock symbols, the data is stored to s3. each s3 parquet file contains the daily values of multiple stock symbols.
2. python aws lambda that queries asx official website to obtain a list of most up to date stock symbols.
3. python module that reads all the s3 historical daily s3 files, joins everything together and return a 1 large in memory polars data table. 
4. python module that ingest the polar data table containing everything. for each stock symbol, it calculates multiple technical indicators recursively/iteratively, performance is not a concern as we are dealing with daily data, not intraday data. it also has classes that take in the dataframe of a single stock symbol and perform backtesting of multiple strategies. each strategy would be stateful on the daily interval and can have action that gets triggered and affect the state of the strategy affecting the portfolio on that single stock.
