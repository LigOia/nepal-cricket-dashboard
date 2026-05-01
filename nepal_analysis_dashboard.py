import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# ==========================================
# 1. 页面配置与基础设置
# ==========================================
st.set_page_config(page_title="Nepal Women Cricket Analytics", layout="wide")


# ==========================================
# 2. 数据加载与预处理
# ==========================================
@st.cache_data
def load_data():
    # 文件路径：您可以直接使用本地同级目录下的文件名，或者填入绝对路径
    file_path = "NepalW2025_2026.xlsx"
    # 如果同级目录下找不到，尝试使用您提供的绝对路径
    if not os.path.exists(file_path):
        file_path = r"C:\Users\li_53\Desktop\板球\2026年亚运会板球女子资格赛\NepalW2025_2026.xlsx"

    try:
        # 读取 Excel 文件的不同 Sheet
        df_match = pd.read_excel(file_path, sheet_name='Sheet1')
        df_bowl = pd.read_excel(file_path, sheet_name='Sheet2')
        df_bat = pd.read_excel(file_path, sheet_name='Sheet3')
    except Exception as e:
        return None, None, None, str(e)

    # --- 预处理 Match Info (Sheet1) ---
    df_match['match_date'] = pd.to_datetime(df_match['match_date'], errors='coerce')
    df_match['year'] = df_match['match_date'].dt.year.astype(str)

    # 更稳健的 Nepal 先攻判断
    def is_nepal_bat_first(row):
        try:
            if row['toss_winner'] == 'Nepal Women':
                return row['toss_choice'] == 'bat'
            else:
                return row['toss_choice'] == 'field'
        except:
            return False

    df_match['nepal_bat_first'] = df_match.apply(is_nepal_bat_first, axis=1)

    # 提取得分
    def get_scores(row):
        if row['nepal_bat_first']:
            return pd.Series([row['first_innings_score'], row['second_innings_score']])
        else:
            return pd.Series([row['second_innings_score'], row['first_innings_score']])

    df_match[['nepal_score', 'opp_score']] = df_match.apply(get_scores, axis=1)

    # 提取统一的对手列用于过滤
    df_match['opponent'] = df_match.apply(
        lambda x: x['team2'] if x['team1'] == 'Nepal Women' else x['team1'], axis=1
    )

    # --- 预处理 Batting (Sheet3) ---
    df_bat['match_date'] = pd.to_datetime(df_bat['match_date'], errors='coerce')
    df_bat['year'] = df_bat['match_date'].dt.year.astype(str)
    df_bat['balls_faced'] = pd.to_numeric(df_bat['balls_faced'], errors='coerce').fillna(0)
    df_bat['strike_rate'] = pd.to_numeric(df_bat['strike_rate'], errors='coerce')
    df_bat['is_not_out'] = df_bat['dismissal_type'].astype(str).str.lower().apply(
        lambda x: True if 'not out' in x or 'retired hurt' in x else False
    )

    # --- 预处理 Bowling (Sheet2) ---
    df_bowl['match_date'] = pd.to_datetime(df_bowl['match_date'], errors='coerce')
    df_bowl['year'] = df_bowl['match_date'].dt.year.astype(str)
    df_bowl['overs_bowled'] = df_bowl['overs_bowled'].astype(str).replace('nan', '0')
    df_bowl['economy_rate'] = pd.to_numeric(df_bowl['economy_rate'], errors='coerce')

    # 避免浮点误差的安全小数超数转换
    def overs_to_decimal(overs_str):
        try:
            parts = str(overs_str).split('.')
            overs = int(parts[0])
            balls = int(parts[1]) if len(parts) > 1 else 0
            return overs + balls / 6.0
        except:
            return 0.0

    df_bowl['dec_overs'] = df_bowl['overs_bowled'].apply(overs_to_decimal)

    # 将 Ground 映射到球员表中
    match_ground_dict = dict(zip(df_match['match_id'], df_match['ground']))
    df_bat['ground'] = df_bat['match_id'].map(match_ground_dict).fillna("Unknown")
    df_bowl['ground'] = df_bowl['match_id'].map(match_ground_dict).fillna("Unknown")

    return df_match, df_bat, df_bowl, ""


df_match, df_bat, df_bowl, error_msg = load_data()

if df_match is None:
    st.error(f"Failed to load Excel file! Error: {error_msg}")
    st.info("Please ensure 'NepalW2025_2026.xlsx' is in the current directory or check the file path.")
    st.stop()

# ==========================================
# 3. 侧边栏：全局筛选器 (Global Filters)
# ==========================================
st.sidebar.title("Global Filters (全局筛选)")

# 提取全局唯一的年份、对手、场地
global_years = sorted(list(set(df_match['year'].dropna().unique()) | set(df_bat['year'].dropna().unique())))
global_opps = sorted(df_match['opponent'].dropna().unique())
global_grounds = sorted(df_match['ground'].dropna().unique())

selected_years = st.sidebar.multiselect("Year (年份)", global_years, default=global_years)
selected_opps = st.sidebar.multiselect("Opponent (对手)", global_opps)
selected_grounds = st.sidebar.multiselect("Ground (场地)", global_grounds)

st.sidebar.markdown("---")
st.sidebar.title("Navigation (导航)")
nav_choice = st.sidebar.radio("Select Module:",
                              ["Overview", "Batting Analysis", "Bowling Analysis", "Player Comparison"])


# 辅助函数：根据全局条件过滤 DataFrame
def apply_global_filters(df, date_col='year', opp_col='opponent', ground_col='ground'):
    mask = df[date_col].isin(selected_years)
    if selected_opps:
        mask &= df[opp_col].isin(selected_opps)
    if selected_grounds:
        mask &= df[ground_col].isin(selected_grounds)
    return df[mask]


# ==========================================
# 4. 模块1: Overview (总体比赛信息)
# ==========================================
if nav_choice == "Overview":
    st.title("Team Overview (球队概况)")

    # 模块专属筛选器
    results_filter = st.sidebar.multiselect("Match Result (比赛结果)", ["won", "lost", "tied", "no result"],
                                            default=["won", "lost"])
    bat_field = st.sidebar.radio("Innings Order (击球顺序)", ["All", "Bat First (先攻)", "Field First (后攻)"])

    # 应用筛选
    f_match = apply_global_filters(df_match)
    if results_filter: f_match = f_match[f_match['result_type'].isin(results_filter)]
    if bat_field == "Bat First (先攻)":
        f_match = f_match[f_match['nepal_bat_first'] == True]
    elif bat_field == "Field First (后攻)":
        f_match = f_match[f_match['nepal_bat_first'] == False]

    total_matches = len(f_match)
    wins = len(f_match[f_match['result_type'] == 'won'])
    win_rate = (wins / total_matches * 100) if total_matches > 0 else 0

    bf_df = f_match[f_match['nepal_bat_first'] == True]
    ff_df = f_match[f_match['nepal_bat_first'] == False]
    bf_win_rate = (len(bf_df[bf_df['result_type'] == 'won']) / len(bf_df) * 100) if len(bf_df) > 0 else 0
    ff_win_rate = (len(ff_df[ff_df['result_type'] == 'won']) / len(ff_df) * 100) if len(ff_df) > 0 else 0

    # KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Matches (总场次)", total_matches)
    c2.metric("Wins & Win Rate (胜场/胜率)", f"{wins} ({win_rate:.1f}%)")
    c3.metric("Bat First Win% (先攻胜率)", f"{bf_win_rate:.1f}%")
    c4.metric("Field First Win% (后攻胜率)", f"{ff_win_rate:.1f}%")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Win Rate: Bat First vs Field First (先后攻胜率)")
        fig1 = go.Figure(data=[
            go.Bar(name='Bat First', x=['Bat First'], y=[bf_win_rate], text=[f"{bf_win_rate:.1f}%"],
                   textposition='auto'),
            go.Bar(name='Field First', x=['Field First'], y=[ff_win_rate], text=[f"{ff_win_rate:.1f}%"],
                   textposition='auto')
        ])
        fig1.update_layout(yaxis_title="Win Rate (%)", template="plotly_white", margin=dict(l=0, r=0, t=30, b=0),
                           showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("Win Rate by Ground (场地胜率 - 场次≥2)")
        ground_stats = f_match.groupby('ground').agg(
            matches=('match_id', 'count'),
            wins=('result_type', lambda x: (x == 'won').sum())
        ).reset_index()
        ground_stats = ground_stats[ground_stats['matches'] >= 2]
        ground_stats['win_rate'] = (ground_stats['wins'] / ground_stats['matches']) * 100
        ground_stats = ground_stats.sort_values('win_rate', ascending=True)

        fig2 = px.bar(ground_stats, x='win_rate', y='ground', orientation='h', text='win_rate',
                      labels={'win_rate': 'Win Rate (%)', 'ground': 'Ground'})
        fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig2.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Nepal Score vs Match Result (尼泊尔得分与胜负关系)")
    threshold_val = st.slider("Select Score Threshold (得分参考线)", min_value=50, max_value=200, value=110, step=5)
    fig3 = px.scatter(f_match, x='match_date', y='nepal_score', color='result_type',
                      labels={'match_date': 'Date', 'nepal_score': 'Nepal Score', 'result_type': 'Result'},
                      hover_data=['opponent', 'ground'], template="plotly_white")
    fig3.add_hline(y=threshold_val, line_dash="dash", line_color="gray", annotation_text=f"Threshold = {threshold_val}")
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Match Details (比赛明细)")
    disp_df = f_match[['match_id', 'match_date', 'opponent', 'result_type', 'result_margin', 'ground']].sort_values(
        'match_date', ascending=False)
    st.dataframe(disp_df, use_container_width=True)

# ==========================================
# 5. 模块2: Batting Analysis (击球分析)
# ==========================================
elif nav_choice == "Batting Analysis":
    st.title("Player Batting Analysis (击球表现分析)")

    players = sorted(df_bat['player_name'].dropna().unique())
    selected_player = st.sidebar.selectbox("Select Player (选择球员)", players)

    f_bat = apply_global_filters(df_bat)
    f_bat = f_bat[f_bat['player_name'] == selected_player]

    innings = len(f_bat)
    total_runs = f_bat['runs_scored'].sum()
    total_balls = f_bat['balls_faced'].sum()
    total_fours = f_bat['fours'].sum()
    total_sixes = f_bat['sixes'].sum()
    not_outs = f_bat['is_not_out'].sum()

    strike_rate = (total_runs / total_balls * 100) if total_balls > 0 else 0
    boundary_pct = ((total_fours + total_sixes) / total_balls * 100) if total_balls > 0 else 0
    four_pct = (total_fours / total_balls * 100) if total_balls > 0 else 0
    six_pct = (total_sixes / total_balls * 100) if total_balls > 0 else 0
    not_out_pct = (not_outs / innings * 100) if innings > 0 else 0

    st.subheader(f"Key Metrics: {selected_player} (核心指标)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Innings (出场次数)", innings)
    c2.metric("Total Runs (总得分)", total_runs)
    c3.metric("Balls Faced (总面对球数)", int(total_balls))
    c4.metric("Strike Rate (打击率)", f"{strike_rate:.2f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Boundary % (边界球率)", f"{boundary_pct:.2f}%")
    c6.metric("4s % (四分球率)", f"{four_pct:.2f}%")
    c7.metric("6s % (六分球率)", f"{six_pct:.2f}%")
    c8.metric("Not Out % (未出局率)", f"{not_out_pct:.1f}%")

    st.markdown("---")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Dismissal Types (出局方式)")


        def map_d_type(d):
            d = str(d).lower()
            if 'not out' in d or 'retired hurt' in d:
                return 'Not Out / Retired (未出局)'
            elif 'c & b' in d:
                return 'Caught & Bowled (接杀并投杀)'
            elif 'st ' in d:
                return 'Stumped (击杀)'
            elif 'run out' in d:
                return 'Run Out (跑杀)'
            elif 'lbw' in d:
                return 'LBW (腿截球)'
            elif d.startswith('b '):
                return 'Bowled (投杀)'
            elif ('c ' in d and ' b ' in d) or d.startswith('c '):
                return 'Caught (接杀)'
            else:
                return 'Other (其他)'


        f_bat = f_bat.copy()
        f_bat['dismissal_category'] = f_bat['dismissal_type'].apply(map_d_type)
        d_counts = f_bat['dismissal_category'].value_counts().reset_index()
        d_counts.columns = ['Dismissal Type', 'Count']

        fig_pie = px.pie(d_counts, names='Dismissal Type', values='Count', hole=0.4)
        fig_pie.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.subheader("Runs Scored Trend (得分趋势)")
        trend_df = f_bat.sort_values('match_date').copy()
        trend_df['sr_label'] = trend_df['strike_rate'].apply(
            lambda x: f"SR:{x:.0f}" if pd.notnull(x) and x > 0 else ""
        )
        fig_line = px.line(trend_df, x='match_date', y='runs_scored', markers=True,
                           labels={'match_date': 'Date (日期)', 'runs_scored': 'Runs Scored (得分)'})
        fig_line.add_trace(go.Scatter(x=trend_df['match_date'], y=trend_df['runs_scored'],
                                      mode='text', text=trend_df['sr_label'],
                                      textposition="top center", showlegend=False))
        fig_line.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("Inning Details (击球明细)")
    disp_bat = f_bat[
        ['match_date', 'opponent', 'runs_scored', 'balls_faced', 'strike_rate', 'fours', 'sixes', 'dismissal_type',
         'ground']].sort_values('match_date', ascending=False)
    st.dataframe(disp_bat, use_container_width=True)

# ==========================================
# 6. 模块3: Bowling Analysis (投球分析)
# ==========================================
elif nav_choice == "Bowling Analysis":
    st.title("Player Bowling Analysis (投球表现分析)")

    bowlers = sorted(df_bowl['player_name'].dropna().unique())
    selected_bowler = st.sidebar.selectbox("Select Bowler (选择投手)", bowlers)

    f_bowl = apply_global_filters(df_bowl)
    f_bowl = f_bowl[f_bowl['player_name'] == selected_bowler]

    total_wickets = f_bowl['wickets_taken'].sum()
    total_dec_overs = f_bowl['dec_overs'].sum()
    total_runs_conceded = f_bowl['runs_conceded'].sum()
    total_maidens = f_bowl['maidens'].sum()
    total_wides = f_bowl['wides'].sum()


    def aggregate_overs_standard(overs_series):
        total_balls = 0
        for o in overs_series:
            try:
                parts = str(o).split('.')
                total_balls += int(parts[0]) * 6
                if len(parts) > 1: total_balls += int(parts[1])
            except:
                pass
        return f"{total_balls // 6}.{total_balls % 6}"


    total_standard_overs = aggregate_overs_standard(f_bowl['overs_bowled'])
    economy_rate = (total_runs_conceded / total_dec_overs) if total_dec_overs > 0 else 0
    maiden_pct = (total_maidens / total_dec_overs * 100) if total_dec_overs > 0 else 0
    wides_per_over = (total_wides / total_dec_overs) if total_dec_overs > 0 else 0

    st.subheader(f"Key Metrics: {selected_bowler} (核心指标)")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Wickets (总出局数)", total_wickets)
    c2.metric("Overs (总局数)", total_standard_overs)
    c3.metric("Runs Conceded (总丢分)", total_runs_conceded)
    c4.metric("Economy Rate (经济率)", f"{economy_rate:.2f}")
    c5.metric("Maiden % (无得分局率)", f"{maiden_pct:.1f}%")
    c6.metric("Wides / Over (均宽球率)", f"{wides_per_over:.2f}")

    st.markdown("---")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Economy Rate Trend (经济率趋势)")
        trend_df = f_bowl.sort_values('match_date').copy()

        # 使用安全的 apply 替换旧版的 np.where -> fillna，避免类型报错
        calculated_eco = trend_df.apply(
            lambda row: row['runs_conceded'] / row['dec_overs'] if row['dec_overs'] > 0 else 0,
            axis=1
        )
        trend_df['match_economy'] = trend_df['economy_rate'].fillna(calculated_eco)

        fig_line = px.line(trend_df, x='match_date', y='match_economy', markers=True,
                           labels={'match_date': 'Date (日期)', 'match_economy': 'Economy Rate (经济率)'},
                           hover_data=['opponent', 'overs_bowled', 'runs_conceded', 'wickets_taken'])
        fig_line.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_line, use_container_width=True)

    with col2:
        st.subheader("Wickets by Opponent (出局数对手分布)")
        wkt_by_opp = f_bowl.groupby('opponent')['wickets_taken'].sum().reset_index()
        wkt_by_opp = wkt_by_opp[wkt_by_opp['wickets_taken'] > 0]

        if not wkt_by_opp.empty:
            fig_pie = px.pie(wkt_by_opp, names='opponent', values='wickets_taken', hole=0.4)
            fig_pie.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No wickets taken in the selected filters. (当前筛选条件下无出局记录)")

    st.subheader("Bowling Details (投球明细)")
    disp_bowl = f_bowl[
        ['match_date', 'opponent', 'overs_bowled', 'runs_conceded', 'wickets_taken', 'maidens', 'wides', 'economy_rate',
         'ground']].sort_values('match_date', ascending=False)
    st.dataframe(disp_bowl, use_container_width=True)

# ==========================================
# 7. 模块4: Player Comparison (球员对比)
# ==========================================
elif nav_choice == "Player Comparison":
    st.title("Player Comparison (球员对比)")

    # 1. 选择角色
    role_choice = st.sidebar.radio("Select Role (选择角色)", ["Batter (击球手)", "Bowler (投球手)"])

    if role_choice == "Batter (击球手)":
        all_batters = sorted(df_bat['player_name'].dropna().unique())
        # 最多选择 5 人
        selected_players = st.sidebar.multiselect(
            "Select Players (选择球员 - 最多5人)",
            all_batters,
            default=all_batters[:2] if len(all_batters) >= 2 else all_batters,
            max_selections=5
        )

        if selected_players:
            # 应用全局过滤并筛选球员
            f_bat = apply_global_filters(df_bat)
            f_bat = f_bat[f_bat['player_name'].isin(selected_players)]

            # 聚合计算
            grp = f_bat.groupby('player_name').agg(
                Innings=('match_id', 'count'),
                Total_Runs=('runs_scored', 'sum'),
                Total_Balls=('balls_faced', 'sum'),
                Total_Fours=('fours', 'sum'),
                Total_Sixes=('sixes', 'sum'),
                Not_Outs=('is_not_out', 'sum')
            ).reset_index()

            # 计算核心指标
            grp['Total_Boundaries'] = grp['Total_Fours'] + grp['Total_Sixes']
            grp['Strike_Rate'] = np.where(grp['Total_Balls'] > 0, grp['Total_Runs'] / grp['Total_Balls'] * 100, 0)
            grp['Boundary_Pct'] = np.where(grp['Total_Balls'] > 0, grp['Total_Boundaries'] / grp['Total_Balls'] * 100,
                                           0)
            grp['Not_Out_Pct'] = np.where(grp['Innings'] > 0, grp['Not_Outs'] / grp['Innings'] * 100, 0)

            # 板球打击均分计算规则：总得分 / (总出场数 - 未出局数)
            outs = grp['Innings'] - grp['Not_Outs']
            grp['Batting_Avg'] = np.where(outs > 0, grp['Total_Runs'] / outs, grp['Total_Runs'])

            st.subheader("Comparison Table (数据对比)")
            st.dataframe(grp[
                ['player_name', 'Innings', 'Total_Runs', 'Strike_Rate', 'Batting_Avg', 'Boundary_Pct']].style.format({
                'Strike_Rate': '{:.2f}',
                'Batting_Avg': '{:.2f}',
                'Boundary_Pct': '{:.2f}%'
            }), use_container_width=True)

            st.subheader("Metrics Visualization (核心指标可视化)")
            metrics_to_plot = {
                "Total_Runs": "Total Runs (总得分)",
                "Batting_Avg": "Batting Average (场均得分)",
                "Strike_Rate": "Strike Rate (打击率)",
                "Boundary_Pct": "Boundary % (边界球率)"
            }

            # 使用 2x2 网格展示分组柱状图
            col1, col2 = st.columns(2)
            for i, (col_name, title) in enumerate(metrics_to_plot.items()):
                fig = px.bar(grp, x='player_name', y=col_name, color='player_name', text_auto='.2f', title=title)
                fig.update_layout(template="plotly_white", showlegend=False, xaxis_title="", yaxis_title="")
                if i % 2 == 0:
                    col1.plotly_chart(fig, use_container_width=True)
                else:
                    col2.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Please select at least one player to compare. (请至少选择一名球员)")

    else:  # 投球手逻辑
        all_bowlers = sorted(df_bowl['player_name'].dropna().unique())
        selected_players = st.sidebar.multiselect(
            "Select Players (选择球员 - 最多5人)",
            all_bowlers,
            default=all_bowlers[:2] if len(all_bowlers) >= 2 else all_bowlers,
            max_selections=5
        )

        if selected_players:
            f_bowl = apply_global_filters(df_bowl)
            f_bowl = f_bowl[f_bowl['player_name'].isin(selected_players)]

            grp = f_bowl.groupby('player_name').agg(
                Matches=('match_id', 'count'),
                Total_Wickets=('wickets_taken', 'sum'),
                Total_Runs_Conceded=('runs_conceded', 'sum'),
                Total_Dec_Overs=('dec_overs', 'sum')
            ).reset_index()

            # 计算核心指标
            grp['Economy_Rate'] = np.where(grp['Total_Dec_Overs'] > 0,
                                           grp['Total_Runs_Conceded'] / grp['Total_Dec_Overs'], 0)
            grp['Wickets_Per_Match'] = np.where(grp['Matches'] > 0, grp['Total_Wickets'] / grp['Matches'], 0)
            # 投球击杀率：每拿下一个出局数需要投出的球数 (越低越好)
            grp['Bowling_SR'] = np.where(grp['Total_Wickets'] > 0, (grp['Total_Dec_Overs'] * 6) / grp['Total_Wickets'],
                                         0)

            st.subheader("Comparison Table (数据对比)")
            st.dataframe(grp[['player_name', 'Matches', 'Total_Wickets', 'Wickets_Per_Match', 'Economy_Rate',
                              'Bowling_SR']].style.format({
                'Economy_Rate': '{:.2f}',
                'Wickets_Per_Match': '{:.2f}',
                'Bowling_SR': '{:.2f}'
            }), use_container_width=True)

            st.subheader("Metrics Visualization (核心指标可视化)")
            metrics_to_plot = {
                "Total_Wickets": "Total Wickets (总出局数)",
                "Wickets_Per_Match": "Wickets per Match (场均出局数)",
                "Economy_Rate": "Economy Rate (经济率 - 越低越好)",
                "Bowling_SR": "Bowling Strike Rate (投球击杀率 - 越低越好)"
            }

            col1, col2 = st.columns(2)
            for i, (col_name, title) in enumerate(metrics_to_plot.items()):
                fig = px.bar(grp, x='player_name', y=col_name, color='player_name', text_auto='.2f', title=title)
                fig.update_layout(template="plotly_white", showlegend=False, xaxis_title="", yaxis_title="")

                # 经济率和击杀率越低越好，可以在图表标题中标注
                if col_name in ["Economy_Rate", "Bowling_SR"]:
                    fig.update_traces(marker_color='indianred')  # 用不同颜色区分“越低越好”的指标

                if i % 2 == 0:
                    col1.plotly_chart(fig, use_container_width=True)
                else:
                    col2.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Please select at least one player to compare. (请至少选择一名球员)")