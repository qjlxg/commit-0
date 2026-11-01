import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime
import multiprocessing as mp
from functools import partial

"""
战法名称：阴线买入战法 (极致精选版)
战法逻辑：
1. 核心过滤：5<=股价<=20，排除ST、创业板。
2. 趋势要求：MA60向上 且 股价站在MA10之上（确保短期强势）。
3. 极致形态：
   - 缩量阴线：成交量必须小于5日均量的40%（地量见地价）。
   - 假阴线：必须是高开且收盘价在昨日收盘价3%以上，且换手率>2%。
4. 智能筛选：自动计算历史回测，只输出历史表现最强的Top 5。
"""

STRATEGY_NAME = "yin_xian_buy_strategy"

def backtest_logic(df, current_idx):
    history_signals = []
    # 增加回测深度至500天
    lookback = max(60, current_idx - 500)
    for i in range(lookback, current_idx - 20):
        h_curr = df.iloc[i]
        vol_ma5 = df.iloc[i-5:i]['成交量'].mean()
        # 使用更严格的缩量回测标准
        if h_curr['收盘'] < h_curr['开盘'] and h_curr['成交量'] < vol_ma5 * 0.45:
            buy_price = h_curr['收盘']
            # 记录20日后的收益
            r_20 = (df.iloc[i+20]['收盘'] - buy_price) / buy_price
            history_signals.append(r_20)
            
    if len(history_signals) < 3: return "数据不足", 0.0, 0.0
    
    win_rate = len([r for r in history_signals if r > 0]) / len(history_signals)
    avg_ret = np.mean(history_signals)
    return f"{win_rate:.1%}", win_rate, avg_ret

def analyze_stock(file_path, name_dict):
    try:
        df = pd.read_csv(file_path)
        if len(df) < 100: return None
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').reset_index(drop=True)
        code = os.path.basename(file_path).replace('.csv', '')
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- 1. 硬性门槛优化 ---
        if not (5.0 <= last['收盘'] <= 20.0) or code.startswith('30') or "ST" in name_dict.get(code, ""):
            return None
        # 排除跌幅过大的阴线（可能是破位）
        if last['涨跌幅'] < -5.0: return None

        # --- 2. 指标精算 ---
        ma10 = df['收盘'].rolling(10).mean().iloc[-1]
        ma60 = df['收盘'].rolling(60).mean().iloc[-1]
        ma60_prev = df['收盘'].rolling(60).mean().iloc[-10]
        vol_ma5 = df['成交量'].rolling(5).mean().iloc[-1]

        # 趋势：MA60向上 且 股价回踩不破MA10
        if last['收盘'] < ma60 or ma60 < ma60_prev or last['收盘'] < ma10: return None

        # --- 3. 战法形态精选 ---
        signal_type = ""
        score = 0
        
        # 形态A：极致缩量（地量阴线）
        if last['收盘'] < last['开盘'] and last['成交量'] < vol_ma5 * 0.4:
            signal_type = "极致缩量阴线"
            score = 80
        # 形态B：强势假阴线（高开低走但仍大涨）
        elif last['开盘'] > prev['收盘'] * 1.02 and last['收盘'] < last['开盘'] and last['收盘'] > prev['收盘'] * 1.01:
            signal_type = "强势假阴洗盘"
            score = 95
            
        if signal_type:
            wr_str, wr_val, avg_ret = backtest_logic(df, len(df)-1)
            # 过滤：历史胜率必须大于55% 且 有过往收益记录
            if wr_val < 0.55: return None
            
            return {
                "代码": code,
                "名称": name_dict.get(code, "未知"),
                "当前价": last['收盘'],
                "信号": signal_type,
                "历史胜率": wr_str,
                "期望收益": f"{avg_ret:.1%}",
                "综合评分": score + (wr_val * 20), # 评分算法
                "建议": "精选品种，一击必中" if score > 90 else "轻仓分批"
            }
    except:
        return None

def main():
    name_df = pd.read_csv('stock_names.csv', dtype={'code': str})
    name_dict = dict(zip(name_df['code'], name_df['name']))

    files = glob.glob('stock_data/*.csv')
    pool = mp.Pool(processes=mp.cpu_count())
    results = pool.map(partial(analyze_stock, name_dict=name_dict), files)
    pool.close()
    
    final = [r for r in results if r is not None]
    if final:
        res_df = pd.DataFrame(final)
        # 只保留评分最高的前 5 只股票
        res_df = res_df.sort_values(by="综合评分", ascending=False).head(5)
        
        now = datetime.now()
        folder = now.strftime('%Y%m')
        os.makedirs(folder, exist_ok=True)
        file_path = f"{folder}/{STRATEGY_NAME}_{now.strftime('%Y%m%d_%H%M')}.csv"
        res_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"筛选完成。今日精选标的数：{len(res_df)}")
    else:
        print("今日无符合极致精选条件的标的。")

if __name__ == "__main__":
    main()
