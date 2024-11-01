#!/bin/sh
$DATABASE_LOCATION='/home/jovyan/src/trade/squeez/eurusd/backtest/data'
$DB_NAME="squeez_eurusd"

cd $DATABASE_LOCATION
echo '.dump'|sqlite3 $DB_NAME|sqlite3 repaired_$DB_NAME
mv $DB_NAME corrupt_$DB_NAME
mv repaired_$DB_NAME $DB_NAME