import pandas as pd
import glob
import os
from datetime import datetime

# ==========================================
# 战法：单阳不破（强势型 vs 中势型）
# 规则：
# 1. 强势型：涨幅>9%, 调整1-3天, 价格在单阳中位线以上
# 2. 中势型：涨幅>9%, 调整4-5天, 价格在单阳最低价以上
# 3. 共同点：缩量调整, 5/10日均线支撑, 剔除调整6天
# ==========================================

def run_strategy():
    # 1. 加载股票名称映射
    names_file = 'stock_names.csv'
    if os.path.exists(names_file):
        names_df = pd.read_csv(names_file, dtype={'code': str})
        name_map = dict(zip(names_df['code'].str.zfill(6), names_df['name']))
    else:
        name_map = {}

    files = glob.glob('stock_data/*.csv')
    results = []

    for f in files:
        try:
            # 读取数据并确保日期排序
            df = pd.read_csv(f)
            df.columns = df.columns.str.strip()
            df = df.sort_values('日期').reset_index(drop=True)
            
            # 基础指标：5/10日均线
            df['MA5'] = df['收盘'].rolling(window=5).mean()
            df['MA10'] = df['收盘'].rolling(window=10).mean()
            
            last_idx = len(df) - 1
            curr_row = df.iloc[last_idx]
            code = str(curr_row['股票代码']).split('.')[0].zfill(6)
            name = name_map.get(code, "未知")

            # 基础过滤：价格5-20元
            if not (5.0 <= curr_row['收盘'] <= 20.0):
                continue

            # 寻找1-5天内的单阳（剔除6天）
            for gap in range(1, 6): 
                yang_idx = last_idx - gap
                if yang_idx < 0: continue
                
                row_yang = df.iloc[yang_idx]
                yang_low = row_yang['最低']
                yang_mid = (row_yang['收盘'] + row_yang['开盘']) / 2
                
                # 调整期数据
                adjust_period = df.iloc[yang_idx + 1:]
                
                # 公共核心：缩量 + 价格不破最低 + 5/10日线支撑
                cond_common = (adjust_period['成交量'] < row_yang['成交量']).all() and \
                              (adjust_period['收盘'] >= yang_low).all() and \
                              (curr_row['收盘'] >= curr_row['MA5'] or curr_row['收盘'] >= curr_row['MA10'])
                
                if not cond_common:
                    continue

                # --- 模式 A: 强势型 (1-3天) ---
                if row_yang['涨跌幅'] >= 9.0 and 1 <= gap <= 3:
                    if (adjust_period['收盘'] >= yang_mid).all():
                        results.append({
                            '代码': code, '名称': name, '类型': '1_强势型(优先)', 
                            '调整天数': gap, '单阳日': row_yang['日期'], '现价': curr_row['收盘']
                        })
                        break
                
                # --- 模式 B: 中势型 (4-5天) ---
                elif row_yang['涨跌幅'] >= 9.0 and 4 <= gap <= 5:
                    results.append({
                        '代码': code, '名称': name, '类型': '2_中势型(稳健)', 
                        '调整天数': gap, '单阳日': row_yang['日期'], '现价': curr_row['收盘']
                    })
                    break
        except:
            continue

    # 3. 处理结果
    if results:
        res_df = pd.DataFrame(results)
        # 按类型(强势在前)和调整天数排序
        res_df = res_df.sort_values(by=['类型', '调整天数'])
        
        # 清洗显示：去掉类型前的排序辅助字符
        res_df['类型'] = res_df['类型'].str.split('_').str[1]
        
        # 打印到控制台（GitHub Action 日志可见）
        print("\n" + "="*50)
        print(f"筛选完成 | 共有 {len(res_df)} 只符合战法个股")
        print("="*50)
        print(res_df.to_string(index=False))
        
        # 保存到 CSV
        save_path = f"Screen_Result_{datetime.now().strftime('%Y%m%d')}.csv"
        res_df.to_csv(save_path, index=False, encoding='utf_8_sig')
    else:
        print("今日无符合战法条件的股票。")

if __name__ == '__main__':
    run_strategy()
