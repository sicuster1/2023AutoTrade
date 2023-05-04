from functools import update_wrapper
import json, config
from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *
from urllib.parse import quote
from json import dumps
import time
from time import sleep
from datetime import datetime

class Binance:
    def __init__(self, public_key = '', secret_key = '', sync = False):
        self.time_offset = 0
        self.b = Client(public_key, secret_key, tld='com')
        #self.b.API_URL = 'https://testnet.binance.vision/api' # for testnet

        if sync:
            self.time_offset = self._get_time_offset()
            print( f"Offset: {self.time_offset} ms")

    def _get_time_offset(self):
        res = self.b.get_server_time()
        return res['serverTime'] - int(time.time() * 1000)

    def synced(self, fn_name, **args):
        args['timestamp'] = int(time.time()*1000 + (self.time_offset))
        res = self.b.get_server_time()
        serverDate = datetime.utcfromtimestamp(res['serverTime'] / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
        clientDate = datetime.utcfromtimestamp(int(args['timestamp'] / 1000.0)).strftime('%Y-%m-%d %H:%M:%S')

        print(f"ClientTime : {clientDate}")
        print(f"ServerTime : {serverDate}")
        print (f"API Request Time = {args['timestamp']}, offset = {self.time_offset}")
        return getattr(self.b, fn_name)(**args)

app = Flask(__name__)
app.debug=True

binanceClient = Binance(config.API_KEY, config.API_SECRET, True)

@app.route('/')
def hello_world():
    return 'Hello from YSB Trade World'

@app.route('/position/resetopen', methods=['POST'])
def webhook_reset():
    #print(request.data)
    data = json.loads(request.data)
    if data['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return{
            "code" : "error",
            "message" : "Nice try, invalid passphrase"
        }

    bar_open_pirce = data['bar']['open']
    bar_cur_price = data['bar']['high']
    order_side = data['strategy']['order_action'].upper()
    order_command = data['strategy']['order_command'].upper()
    order_division = data['strategy']['order_division']
    order_ticker = data['ticker']

    print(order_ticker)
    print(order_side)
    print(order_command)
    print(bar_cur_price)
    print(order_division)

    #order_stop_price = calcstopprice(order_side, bar_cur_price, order_stop_percent, 4)

    position = getpositions(order_ticker)
    print(position)

    position_amt = float(position['positionAmt'])
    position_notional = float(position['notional'])
    position_entry_price = float(position['entryPrice'])
    position_side = getpoitionside(position_amt)
    position_leverage = position['leverage']

    print('>>>>> Open Poisition Info <<<<<')
    print(f'     [notional] : {position_notional}, [amt] : {position_amt}, [entry] : {position_entry_price}, [side] : {position_side}')

    
    if position_side.upper() != 'ZERO':
        #대기중인 주문 종료 
        binanceClient.synced('futures_cancel_all_open_orders', symbol=order_ticker, recvwindow=60000)
        # 현재 포지션 종료 
        close_amt = closecommand('FULL', position_amt)
        close_responce = closeOrder(changeside(position_side), float(round(close_amt, 0)), order_ticker)
        if close_responce == False : 
             print("close order failed")
             return {
                "code": "closeorder",
                "error"  : "error",
                "message": "close order failed",
             }

    # 잔고계산
    usdt_balance = float(calcBalanceCommand('USDT', position_leverage, order_command, order_division))
    print(f'>>>>> usdt * leverage = {usdt_balance}')
    #usdt_balance = 5000
    order_final_amt_round = usdt_balance / bar_cur_price
    order_final_amt = float(round(order_final_amt_round, symbolPrecision(order_ticker)))
  
    # 테스트 시 사용 Amount
    #order_final_amt = 1000

    print(f'>>>>> calcuate final, usdt_balance = {usdt_balance}, order_final_amt = {order_final_amt}')
        
    # 진입주문
    #order_first_balance = float(round((order_final_amt), 0)) 
    order_response= order(order_side, order_final_amt, order_ticker, ORDER_TYPE_MARKET)
    print(order_response)
    if order_response == False :
        print("order failed")
        return {
            "code": "order",
            "error"  : "error",
            "message": "order failed",
            }
    else :
        print("order excute success")
        return {
        "code": "success",
        "error"  : "",
        "message": "order excute success",
        }


    
    # 손절주문 1
    # order_stop_price = calcstopprice(order_side, bar_cur_price, float(2.5), 4)
    # stop_order_res1 = stopOrder(changeside(order_side), order_final_amt/2, order_ticker, order_stop_price)
    # print(stop_order_res1)
    # if stop_order_res1 == False :
    #     print("stop order1 failed")
    #     return {
    #         "code": "stop order1 ",
    #         "error"  : "error",
    #         "message": "stop order1 failed",
    # }

    # 손절주문 2
    # order_stop_price = calcstopprice(order_side, bar_cur_price, float(2.0), 4)
    # stop_order_res2 = stopOrder(changeside(order_side), order_final_amt/2, order_ticker, order_stop_price)
    # print(stop_order_res2)
    # if stop_order_res2 == False :
    #     print("stop order2 failed")
    #     return {
    #         "code": "stop order2 ",
    #         "error"  : "error",
    #         "message": "stop order2 failed",
    #     }
    # else :
    #     print("order success")
    #     return {
    #         "code": "order",
    #         "error"  : "success",
    #         "message": "all order success",
    #     }


@app.route('/position/close', methods=['POST'])
def webhookClose():
    #print(request.data)
    data = json.loads(request.data)
    if data['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return{
            "code" : "error",
            "message" : "Nice try, invalid passphrase"
        }

    print(data['ticker'])
    print(data['bar'])
    print(data['strategy']['order_command'])

    
    order_ticker = data['ticker']
    order_command = data['strategy']['order_command']

    print('>>>>> Close Order Info <<<<<')
    print(f'     [ticker] : {order_ticker}, [command] : {order_command}')
    
    position = getpositions(order_ticker)
    print(position)

    position_amt = float(position['positionAmt'])
    position_entry_price = float(position['entryPrice'])
    position_side = getpoitionside(position_amt)

   
    print('>>>>> Close Poisition Info <<<<<')
    print(f'     [amt] : {position_amt}, [entry] : {position_entry_price}, [side] : {position_side}')

    order_final_amt = closecommand(order_command, position_amt)
    
    

    order_response =closeOrder(changeside(position_side), float(round(order_final_amt, 0)), order_ticker)

    print(order_response)

    if order_response :
        return {
            "code": "success",
            "messge": "closeorder excute",
            "amount" : order_final_amt
            #"compare_side": compare_side
        }
    else :
        print("order failed")
        return {
            "code": "error",
            "message": "cloeorder failed",
            #"compare_side" : compare_side
        }

@app.route('/position/check', methods=['POST'])
def webhookCheck():
    data = json.loads(request.data)
    if data['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return{
            "code" : "error",
            "message" : "Nice try, invalid passphrase"
        }
    
    
    order_side = data['strategy']['order_action'].upper()
    order_ticker = data['ticker']
   
    print(f'1. Open Poisition Check, Ticker = {order_ticker}, Side = {order_side}')

  
    position = getpositions(order_ticker)
    print(position)
    
    position_amt = float(position['positionAmt'])
    position_side = getpoitionside(position_amt)
    position_notional = float(position['notional'])
    position_entry_price = float(position['entryPrice'])
    position_leverage = position['leverage']

    
    print(f' 1-1.Check Result [notional] : {position_notional}, [amt] : {position_amt}, [entry] : {position_entry_price}, [side] : {position_side}')

    if order_side != position_side : 
        #webhook_reset()
        bar_open_pirce = data['bar']['open']
        bar_cur_price = data['bar']['high']
        order_side = data['strategy']['order_action'].upper()
        order_command = data['strategy']['order_command'].upper()
        order_division = data['strategy']['order_division']
        order_ticker = data['ticker']

        print(order_ticker)
        print(order_side)
        print(order_command)
        print(bar_cur_price)
        print(order_division)

        if position_side.upper() != 'ZERO':
            #대기중인 주문 종료 
            binanceClient.synced('futures_cancel_all_open_orders', symbol=order_ticker, recvwindow=60000)
            # 현재 포지션 종료
            print('2. Current Position Closed') 
            close_amt = closecommand('FULL', position_amt)
            close_responce = closeOrder(changeside(position_side), float(round(close_amt, 0)), order_ticker)
            if close_responce == False : 
                print("close order failed")
                return {
                    "code": "closeorder",
                    "error"  : "error",
                    "message": "close order failed",
                }

        # 잔고계산
        
        usdt_balance = float(calcBalanceCommand('USDT', position_leverage, order_command, order_division))
        print(f'>>>>> usdt * leverage = {usdt_balance}')
        order_final_amt_round = usdt_balance / bar_cur_price
        order_final_amt = float(round(order_final_amt_round, symbolPrecision(order_ticker)))    
        print(f'3. Calculate Final Order, usdt_balance = {usdt_balance}, order_final_amt = {order_final_amt}')
        # 테스트 시 사용 Amount
        # order_final_amt = 1000

        

        # 진입주문
        #order_first_balance = float(round((order_final_amt), 0)) 
        print(f'4. Try Final Order, Side = {order_side}, Ticker = {order_ticker}, Amt = {order_final_amt}')
        order_response= order(order_side, order_final_amt, order_ticker, ORDER_TYPE_MARKET)

        print(order_response)
        if order_response == False :
            print("order failed")
            return {
                "code": "order",
                "error"  : "error",
                "message": "order failed",
            }
        else :
            print("order excute success")
            return {
            "code": "success",
            "error"  : "",
            "message": "order excute success",
        }

        return {
            "code": "success",
            "messge": "check order excute",
            #"compare_side": compare_side
        }
    else:
        return {
            "code": "fail",
            "messge": "order == postion same side",
            #"compare_side": compare_side
        }

# @app.route('/position/reverse', methods=['POST'])
# def webhookReverse():
#     data = json.loads(request.data)
#     if data['passphrase'] != config.WEBHOOK_PASSPHRASE:
#         return{
#             "code" : "error",
#             "message" : "Nice try, invalid passphrase"
#         }
    
#     #order_side = data['strategy']['order_action'].upper()
#     order_ticker = data['ticker']

#     print(order_ticker)
#     #print(order_side)
    
#     bar_open_pirce = data['bar']['open']
#     bar_cur_price = data['bar']['high']
#     #order_side = data['strategy']['order_action'].upper()
#     order_command = data['strategy']['order_command'].upper()
#     order_division = data['strategy']['order_division']
#     order_ticker = data['ticker']

#     print(order_ticker)
#     #print(order_side)
#     print(order_command)
#     print(bar_cur_price)
#     print(order_division)

#     position = getpositions(order_ticker)
#     print(position)

#     position_amt = float(position['positionAmt'])
#     position_notional = float(position['notional'])
#     position_entry_price = float(position['entryPrice'])
#     position_side = getpoitionside(position_amt)
#     position_leverage = position['leverage']

#     print('>>>>> Open Poisition Info <<<<<')
#     print(f'     [notional] : {position_notional}, [amt] : {position_amt}, [entry] : {position_entry_price}, [side] : {position_side}')

    
#     if position_side.upper() != 'ZERO':
#         #대기중인 주문 종료 
#         binanceClient.futures_cancel_all_open_orders(symbol=order_ticker, recvwindow=60000)
#         # 현재 포지션 종료 
#         close_amt = closecommand('FULL', position_amt)
#         close_responce = closeOrder(changeside(position_side), float(round(close_amt, 0)), order_ticker)
#         if close_responce == False : 
#              print("close order failed")
#              return {
#                 "code": "closeorder",
#                 "error"  : "error",
#                 "message": "close order failed",
#              }

#     # 잔고계산
#     usdt_balance = float(calcBalanceCommand('USDT', position_leverage, order_command, order_division))
#     print(f'>>>>> usdt * leverage = {usdt_balance}')
#     #usdt_balance = 5000
#     order_final_amt_round = usdt_balance / bar_cur_price
#     order_final_amt = float(round(order_final_amt_round, symbolPrecision(order_ticker)))
  
#     # 테스트 시 사용 Amount
#     #order_final_amt = 1000

#     print(f'>>>>> calcuate final, usdt_balance = {usdt_balance}, order_final_amt = {order_final_amt}')
        
#     # 진입주문
#     #order_first_balance = float(round((order_final_amt), 0)) 
#     order_response= order(changeside(position_side), order_final_amt, order_ticker, ORDER_TYPE_MARKET)
#     print(order_response)
#     if order_response == False :
#         print("order failed")
#         return {
#             "code": "order",
#             "error"  : "error",
#             "message": "order failed",
#             }
#     else :
#         print("order excute success")
#         return {
#         "code": "success",
#         "error"  : "",
#         "message": "order excute success",
#         }

############################################################################### API End ############################################################################

def order(side, quantity, symbol, order_type):
    try:
        print(f">>>>> Order Excute <<<<<<")
        print(f"[OrderType] = {order_type}, [Symbol] = {symbol}, [Side] = {side}, [Quantity] = {quantity}")
        order = binanceClient.synced('futures_create_order', symbol=symbol, type=order_type, side=side, quantity=quantity, recvwindow=60000)
        #order = client.futures_create_order(symbol='ADAUSDT', side=SIDE_SELL, type=FUTURE_ORDER_TYPE_STOP_MARKET, quantity=quantity, positionside='BOTH', stopPrice=float(round(0.44203, 4)), timeInForce=TIME_IN_FORCE_GTC)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return order

def limitOrder(side, quantity, symbol, order_type, price):
    try:
        print(f">>>>> Limit Order Excute <<<<<<")
        print(f"[OrderType] = {order_type}, [Symbol] = {symbol}, [Side] = {side}, [Quantity] = {quantity}, [Price] = {price}")
        order = binanceClient.futures_create_order( symbol=symbol, type=order_type, side=side, quantity=quantity, price=price, positionside='BOTH', timeInForce=TIME_IN_FORCE_GTC, recvwindow=60000)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return order

def stopOrder(side, quantity, symbol, order_stop_price):
    try:
        stopPrice_=float(round(order_stop_price, 4))
        quantity_=float(round(quantity,2))
        print(f">>>>> stopOrder Excute <<<<<")
        print(f"[OrderType] = {'FUTURE_ORDER_TYPE_STOP_MARKET'}, [Symbol] = {symbol}, [Side] = {side}, [Quantity] = {quantity}, [StopPrice] = {stopPrice_}")
        stopOrder = binanceClient.synced('futures_create_order', symbol=symbol, side=side, type=FUTURE_ORDER_TYPE_STOP_MARKET, quantity = quantity_, positionside='BOTH', timeInForce=TIME_IN_FORCE_GTC, stopprice = stopPrice_, recvwindow=60000)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return stopOrder

def closeOrder(side, quantity, symbol, order_type=ORDER_TYPE_MARKET):
    try:
        print(f">>>>>>> CloseOrder <<<<<<")
        print(f"{order_type} -{symbol} {side} {quantity}")
        order = binanceClient.synced('futures_create_order',symbol=symbol, type='MARKET', side=side, quantity=quantity, reduceOnly='true', recvwindow=60000)
        print(order)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return order

def getpositions(symbol):
    try:
        print(f">>>>> Get Positions, [symbol] = {symbol}")
        res = binanceClient.synced('futures_account', recvwindow=60000)
        positions = res['positions']
        for position in positions:
            if symbol == position['symbol']:
                print(position)
                return position
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False
    
    return False

def getpoitionside(positionamt):
    if positionamt > 0:
        return 'BUY'
    elif positionamt < 0:
        return 'SELL'
    else :
        return 'ZERO'

def closecommand(command, positonAmt) :
    # postion_amt 가 음수인경우에 -1곱하기
    calc_amt =0
    if positonAmt < 0 :
        calc_amt = positonAmt * -1
    else :
        calc_amt = positonAmt
    if command.upper() == 'FULL':
        print('closecommnd-FULL')
        return float(calc_amt) + float(1)
    elif command.upper() == 'HALF':
        print('closecommnd-HALF')
        return float(calc_amt)/2
    elif command.upper() == 'QUTOR':
        print('closecommnd-QUTOR')
        return float(calc_amt)/4
    elif command.upper() == '10TH':
        print('closecommnd-10TH')
        return float(calc_amt)/13
    else:
        print("ERROR - closecommand is zero")
        return 0



#풀시드 기준 명령(FULL/HALF/QUOT/10th)
def calcBalanceCommand(symbol, lever, comm, division):
    cur_balance = getBalance(symbol, lever, division)
    if comm.upper() == '10TH':
        return (cur_balance/20)-10
    elif comm.upper() == 'QUOT':
        return (cur_balance/4)-10
    elif comm.upper() == 'HALF':
        return (cur_balance/2)-10
    elif comm.upper() == 'FULL':
        return cur_balance-(cur_balance /50)

#풀시드 풀 주문
def getBalance(symbol, lever, division):
    balance = binanceClient.synced('futures_account_balance', recvwindow=60000)
    print(balance)
    for check_balance in balance:
        if check_balance["asset"] == symbol.upper():
            balance = check_balance["balance"]
            withdraw = check_balance["withdrawAvailable"]
            print(f'request Symbol - {symbol.upper()}, balance = {float(balance)}, withdraw = {withdraw}, lever = {lever}') # Prints 0.0000
            return checkMinimumBalance(balance, withdraw, division)*float(lever)

def checkMinimumBalance(balance, withdraw, division):
    calc_balance = float(balance)/division
    if float(calc_balance) < float(withdraw) :
        return float(calc_balance)
    else : 
        return float(withdraw)

# 손절 가격 계산
def calcstopprice(order_side, order_price, percent, precsion):
    if order_side.upper() == 'BUY' :
        stop_price = float(order_price) - (float(order_price) * (float(percent)/100) )
    else:
        stop_price = float(order_price) + (float(order_price) * (float(percent)/100) )
    return float(round(stop_price,precsion))

# 포지션 방향 전환
def changeside(side) :
    if side.upper() == 'BUY':
        return 'SELL'
    else:
        return 'BUY'

#주문가격 진입 체크 
def checkentry(entry_price, current_price, postion_amt):
    if postion_amt < 0:
        if entry_price < current_price: 
            return True
        else:
            return False
    elif postion_amt > 0:
        if entry_price > current_price: 
            return True
        else:
            return False
    else:
        return True

#방향성 주문
def orderPositionCheck(order_ticker, order_amt, order_1st_amt, order_side, order_limit, pos_side, pos_entry_price, pos_amt, bar_cur_price ):
    order_final_amt=0
    position_amt_temp = pos_amt
    error ='NoError'
    #포지션이 0 일때
    if pos_side == 'ZERO':
        binanceClient.futures_cancel_all_open_orders(symbol=order_ticker, recvwindow=60000)
        print("account value Zero")
        order_final_amt = float(order_1st_amt)
        return order_final_amt
    # 포지션방향 == 주문방향
    elif pos_side == order_side:
            if checkentry(float(pos_entry_price), float(bar_cur_price), float(pos_amt)) == True:
                if pos_amt < float(0) :
                    position_amt_temp = pos_amt *-1
                if position_amt_temp < order_limit :
                    order_final_amt = order_amt
                    return order_final_amt
                else:
                    error ="order amt is invalid limit"
                    order_final_amt = 0.0
                    print(error)
                    return order_final_amt
            else:
               error = "order current price check not entry" 
               order_final_amt = 0.0
               print(error)
               return order_final_amt
    # 포지션방향 과 주문방향이 다를때
    else:
        binanceClient.futures_cancel_all_open_orders(symbol=order_ticker, recvwindow=60000)
        close_amt = closecommand("ALL", pos_amt, order_amt)
        closeOrder(order_side, close_amt, order_ticker)
        order_final_amt = float(order_1st_amt)
        return order_final_amt

def symbolPrecision(symbol) :
    if symbol.upper() == 'ETHUSDT' :
        return 3
    elif symbol.upper() == 'XRPUSDT':
        return 1
    elif symbol.upper() == 'BTCUSDT':
        return 3

if __name__ == "__main__":
    app.run()
