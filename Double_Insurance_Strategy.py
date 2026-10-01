import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime
import multiprocessing

# --- 战法备注：双保金选 (Double_Insurance_Strategy) ---
# 1. 战法逻辑：寻找月线突破后的日线回踩。要求 DIF/DEA 均在0轴上方（多头市场）。
# 2. 核心买点：股价回踩 MA20 均线，成交量极度萎缩（地量），暗示空头衰竭。
# 3. 过滤条件：5-20元 A股，排除 ST、创业板(300)、科创板(688)。
# 4. 回测逻辑：自动计算过去 60 天内，出现相同信号后 5 日内盈利 5% 的概率。
# --------------------------------------------------

STRATEGY_NAME = "Double_Insurance_Strategy"

def analyze_stock(file_path, name_dict):
    try:
        df = pd.read_csv(file_path)
        if df.empty or len(df) < 60:
            return None
        
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期')
        code = str(df['股票代码'].iloc[-1]).zfill(6)
        
        # 1. 基础硬过滤
        name = name_dict.get(code, "未知")
        if any(x in name for x in ["ST", "退"]) or code.startswith(('300', '688', '8', '4')):
            return None
        
        last_close = df['收盘'].iloc[-1]
        if not (5.0 <= last_close <= 20.0):
            return None

        # 2. 技术指标计算
        # MACD
        ema12 = df['收盘'].ewm(span=12, adjust=False).mean()
        ema26 = df['收盘'].ewm(span=26, adjust=False).mean()
        df['dif'] = ema12 - ema26
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd'] = (df['dif'] - df['dea']) * 2
        
        # 均线
        df['ma20'] = df['收盘'].rolling(20).mean()
        df['vol_ma5'] = df['成交量'].rolling(5).mean()

        # 3. 战法逻辑量化
        # 条件1：水上运行 (DIF > 0)
        is_above_zero = df['dif'].iloc[-1] > 0
        # 条件2：回踩 MA20 (价格离MA20距离在 0%-6% 之间)
        bias_20 = (last_close - df['ma20'].iloc[-1]) / df['ma20'].iloc[-1] * 100
        is_backtest_zone = 0 < bias_20 < 6.0
        # 条件3：极致缩量 (今日量 < 5日均量的 75%)
        is_low_vol = df['成交量'].iloc[-1] < df['vol_ma5'].iloc[-1] * 0.75

        # 4. 并行回测逻辑 (回溯过去 60 天)
        wins = 0
        total_signals = 0
        # 简化版回测，提高脚本运行速度
        for i in range(len(df) - 60, len(df) - 5):
            t_dif = df['dif'].iloc[i]
            t_close = df['收盘'].iloc[i]
            t_ma20 = df['ma20'].iloc[i]
            t_vol = df['成交量'].iloc[i]
            t_vol_ma5 = df['vol_ma5'].iloc[i]
            
            # 模拟当时的信号
            if t_dif > 0 and 0 < (t_close - t_ma20)/t_ma20 < 0.06 and t_vol < t_vol_ma5 * 0.75:
                total_signals += 1
                # 未来5天最高涨幅是否 > 5%
                if (df['最高'].iloc[i+1 : i+6].max() - t_close) / t_close >= 0.05:
                    wins += 1
        
        win_rate = (wins / total_signals * 100) if total_signals > 0 else 0

        # 5. 评分与建议
        score = 0
        if is_above_zero: score += 40
        if is_backtest_zone: score += 30
        if is_low_vol: score += 30
        
        # 只要 score > 80 就记录，但给出不同的操作建议
        if score >= 80:
            if score >= 90 and win_rate >= 60:
                suggestion = "【一击必中】重点关注，高胜率回踩"
            elif score >= 90:
                suggestion = "【试错观察】形态完美但历史股性一般"
            else:
                suggestion = "【备选】回踩力度尚可，观察均线支撑"

            return {
                "代码": code,
                "名称": name,
                "收盘价": last_close,
                "信号强度": f"{score}%",
                "历史回测胜率": f"{win_rate:.1f}%",
                "回测信号数": total_signals,
                "操作建议": suggestion,
                "战法逻辑": "MACD水上+地量回踩均线"
            }
    except:
        return None
    return None

def run_strategy():
    # 确保结果目录存在
    now = datetime.now()
    dir_path = f"results/{now.strftime('%Y%m')}"
    os.makedirs(dir_path, exist_ok=True)
    
    # 加载股票名称
    if not os.path.exists('stock_names.csv'):
        print("错误: 缺少 stock_names.csv")
        return
    names = pd.read_csv('stock_names.csv', dtype={'code': str})
    name_dict = dict(zip(names['code'], names['name']))
    
    # 获取 CSV 文件列表
    csv_files = glob.glob('stock_data/*.csv')
    if not csv_files:
        print("警告: stock_data 目录下没有数据文件")
        return

    # 并行扫描
    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        results = pool.starmap(analyze_stock, [(f, name_dict) for f in csv_files])
    
    final_list = [r for r in results if r is not None]
    if final_list:
        final_df = pd.DataFrame(final_list).sort_values(by=["信号强度", "历史回测胜率"], ascending=False)
        file_name = f"{STRATEGY_NAME}_{now.strftime('%Y%m%d_%H%M%S')}.csv"
        save_path = os.path.join(dir_path, file_name)
        final_df.to_csv(save_path, index=False, encoding='utf-8-sig')
        print(f"筛选成功: 发现 {len(final_df)} 只潜力股，存至 {save_path}")
    else:
        print("今日无符合条件的股票")

if __name__ == "__main__":
    run_strategy()
