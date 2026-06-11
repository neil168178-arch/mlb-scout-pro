import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import plotly.express as px
import unicodedata
from pybaseball import statcast_batter_expected_stats, statcast_pitcher_expected_stats, statcast_batter_exitvelo_barrels, statcast_pitcher_exitvelo_barrels, statcast_batter, statcast_pitcher
from datetime import datetime, timedelta, timezone

# 🌟 必須是第一個 Streamlit 指令
st.set_page_config(layout="wide", page_title="MLB 球探系統")

# --- 0. 常數與全域設定 ---
MLB_TEAM_COLORS = {
    "Los Angeles Dodgers": ("#005A9C", "#A5ACAF"), "New York Yankees": ("#0C2340", "#C4CED4"),
    "Boston Red Sox": ("#BD3039", "#0C2340"), "Houston Astros": ("#EB6E1F", "#002D62"),
    "Atlanta Braves": ("#CE1141", "#13274F"), "Philadelphia Phillies": ("#E81828", "#002D72"),
    "New York Mets": ("#FF5910", "#002D72"), "Toronto Blue Jays": ("#134A8E", "#1D2D5C"),
    "Baltimore Orioles": ("#DF4601", "#000000"), "Tampa Bay Rays": ("#092C5C", "#8FBCE6"),
    "Chicago White Sox": ("#27251F", "#C4CED4"), "Cleveland Guardians": ("#E31937", "#0C2340"),
    "Detroit Tigers": ("#0C2340", "#FA4616"), "Kansas City Royals": ("#004687", "#BD9B60"),
    "Minnesota Twins": ("#002B5C", "#D31145"), "Los Angeles Angels": ("#BA0021", "#003263"),
    "Oakland Athletics": ("#003831", "#EFB21E"), "Seattle Mariners": ("#005C5C", "#0C2C56"),
    "Texas Rangers": ("#003278", "#C0111F"), "Chicago Cubs": ("#0E3386", "#CC3433"),
    "Cincinnati Reds": ("#C6011F", "#000000"), "Milwaukee Brewers": ("#FFC52F", "#12284B"),
    "Pittsburgh Pirates": ("#FDB827", "#27251F"), "St. Louis Cardinals": ("#C41E3A", "#0C2340"),
    "Arizona Diamondbacks": ("#A71930", "#E3D4AD"), "Colorado Rockies": ("#333366", "#C4CED4"),
    "San Diego Padres": ("#2F241D", "#FFC425"), "San Francisco Giants": ("#FD5A1E", "#27251F"),
    "Miami Marlins": ("#00A3E0", "#EF3340"), "Washington Nationals": ("#AB0003", "#14225A"),
}

MLB_TEAM_IDS = {
    "Los Angeles Dodgers": 119, "New York Yankees": 147, "Boston Red Sox": 111,
    "Houston Astros": 117, "Atlanta Braves": 144, "Philadelphia Phillies": 143,
    "New York Mets": 121, "Toronto Blue Jays": 141, "Baltimore Orioles": 110,
    "Tampa Bay Rays": 139, "Chicago White Sox": 145, "Cleveland Guardians": 114,
    "Detroit Tigers": 116, "Kansas City Royals": 118, "Minnesota Twins": 142,
    "Los Angeles Angels": 108, "Oakland Athletics": 133, "Seattle Mariners": 136,
    "Texas Rangers": 140, "Chicago Cubs": 112, "Cincinnati Reds": 113,
    "Milwaukee Brewers": 158, "Pittsburgh Pirates": 134, "St. Louis Cardinals": 138,
    "Arizona Diamondbacks": 109, "Colorado Rockies": 115, "San Diego Padres": 135,
    "San Francisco Giants": 137, "Miami Marlins": 146, "Washington Nationals": 120,
}

grade_keys = ['S', 'A_plus_plus', 'A_plus', 'A', 'B_plus_plus', 'B_plus', 'B', 'C', 'D', 'E', 'F']
grade_defaults = ['#FFD700', '#FF3300', '#FF6600', '#FF9900', '#0033CC', '#0066FF', '#3399FF', '#2E8B57', '#808080', '#A9A9A9', '#555555']
grade_to_key = {'S': 'S', 'A++': 'A_plus_plus', 'A+': 'A_plus', 'A': 'A', 'B++': 'B_plus_plus', 'B+': 'B_plus', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F'}

if 'font_size' not in st.session_state: st.session_state.font_size = 15
if 'table_font_size' not in st.session_state: st.session_state.table_font_size = 13
for k, c in zip(grade_keys, grade_defaults):
    if f'color_{k}' not in st.session_state: 
        st.session_state[f'color_{k}'] = c

# --- 1. 核心工具函數與樣式函數 ---
def clean_name(name):
    if not isinstance(name, str): return ""
    return unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

def get_team_color(team_name, default_colors=("#EF3E42", "#1E90FF")):
    if not team_name: return default_colors
    if team_name in MLB_TEAM_COLORS: return MLB_TEAM_COLORS[team_name]
    for full_name, colors in MLB_TEAM_COLORS.items():
        if full_name.split()[-1] in team_name or team_name in full_name:
            return colors
    if "Athletics" in team_name or "A's" in team_name: return ("#003831", "#EFB21E")
    return default_colors

def get_team_logo_url(team_name):
    if not team_name: return ""
    tid = None
    if team_name in MLB_TEAM_IDS:
        tid = MLB_TEAM_IDS[team_name]
    else:
        for full_name, i in MLB_TEAM_IDS.items():
            if full_name.split()[-1] in team_name or team_name in full_name:
                tid = i
                break
        if not tid and ("Athletics" in team_name or "A's" in team_name): tid = 133
    return f"https://www.mlbstatic.com/team-logos/{tid}.svg" if tid else ""

def hex_to_rgba(hex_color, alpha=0.08):
    if not hex_color or not isinstance(hex_color, str): return "rgba(0,0,0,0)"
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r}, {g}, {b}, {alpha})"
    return "rgba(0,0,0,0)"

def score_to_grade(s):
    if pd.isna(s): return 'F'
    if s >= 9.5: return 'S'
    elif s >= 9.0: return 'A++'
    elif s >= 8.0: return 'A+'
    elif s >= 7.0: return 'A'
    elif s >= 6.0: return 'B++'
    elif s >= 5.0: return 'B+'
    elif s >= 4.0: return 'B'
    elif s >= 3.0: return 'C'
    elif s >= 2.0: return 'D'
    elif s >= 1.0: return 'E'
    else: return 'F'

def get_percentile(df, col_name, val, p_type):
    if p_type == '打者': lower_is_better = ['Chase%', 'Whiff%', 'GB%', 'K%']
    else: lower_is_better = ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
    series = df[col_name].dropna()
    if len(series) == 0: return 0
    pct = (series >= val).mean() if col_name in lower_is_better else (series <= val).mean()
    return round(pct * 100, 1)

def get_relative_grade(df, col_name, val, p_type):
    if p_type == '打者': lower_is_better = ['Chase%', 'Whiff%', 'GB%', 'K%']
    else: lower_is_better = ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
    series = df[col_name].dropna()
    if len(series) == 0: return 'C', 3
    pct = (series >= val).mean() if col_name in lower_is_better else (series <= val).mean()
    grades = {'S': (0.95, 10), 'A++': (0.90, 9), 'A+': (0.80, 8), 'A': (0.70, 7), 'B++': (0.60, 6), 'B+': (0.50, 5), 'B': (0.40, 4), 'C': (0.30, 3), 'D': (0.20, 2), 'E': (0.10, 1), 'F': (0, 0)}
    for g, (p, s) in grades.items():
        if pct >= p: return g, s
    return 'F', 0

def safe_float(val):
    try: return float(val)
    except: return 0.0

def generate_scout_conclusion(prs, war, p_type):
    pr_barrel = prs.get('Barrel%', 50)
    pr_hardhit = prs.get('HardHit%', 50)
    pr_whiff = prs.get('Whiff%', 50)
    pr_chase = prs.get('Chase%', 50)
    pr_gb = prs.get('GB%', 50)
    pr_xba = prs.get('xBA', 50)
    pr_k = prs.get('K%', 50)
    pr_bb = prs.get('BB%', 50)
    
    if p_type == '打者':
        if war >= 7.0: tier = "歷史級"
        elif war >= 5.0: tier = "MVP級"
        elif war >= 3.0: tier = "全明星級"
        elif war >= 1.5: tier = "先發主力"
        elif war >= 0.0: tier = "板凳待命"
        else: tier = "掙扎中"
        
        if pr_whiff >= 80 and pr_chase >= 80: adj = "選球精湛的"
        elif pr_whiff >= 65: adj = "黏球纏鬥的"
        elif pr_whiff <= 20: adj = "電風扇式的"
        elif pr_gb <= 20: adj = "強力滾地的" 
        elif pr_gb >= 80: adj = "極端飛球的"
        elif pr_xba >= 80: adj = "高打擊率的"
        else: adj = "風格均衡的"
        
        if pr_barrel >= 95: noun = "核彈巨砲"
        elif pr_barrel >= 80: noun = "恐怖重砲"
        elif pr_hardhit >= 75: noun = "強擊球製造機"
        elif pr_barrel <= 20: noun = "碰碰槍"
        else: noun = "實用打者"
        return f"{tier}{adj}{noun}"
    else:
        if war >= 6.0: tier = "神獸級"
        elif war >= 4.0: tier = "賽揚級"
        elif war >= 2.5: tier = "全明星級"
        elif war >= 1.0: tier = "主力輪值/穩健牛棚"
        elif war >= 0.0: tier = "工作馬"
        else: tier = "掙扎中"
        
        if pr_bb >= 85: adj = "雷達導航般的"
        elif pr_bb >= 65: adj = "控球穩健的"
        elif pr_bb <= 20: adj = "狂野亂放的"
        elif pr_gb >= 80: adj = "製造滾地的" 
        elif pr_gb <= 20: adj = "飛球派的"
        else: adj = "表現均衡的"
        
        if pr_k >= 95: noun = "三振魔人"
        elif pr_k >= 80: noun = "K博士"
        elif pr_whiff >= 80: noun = "揮空引誘大師"
        elif pr_hardhit >= 80: noun = "軟投派大師"
        elif pr_k <= 20: noun = "發球機"
        else: noun = "實力派投手"
        return f"{tier}{adj}{noun}"

def highlight_elite_stats(val, col_name, p_type):
    style = ''
    if pd.isna(val) or not isinstance(val, (int, float)): return style
    if col_name == 'WAR' and val >= 5.0: return 'color: #EF3E42; font-weight: bold;'
    if p_type == '打者':
        if col_name == 'Barrel%' and val >= 12.0: style = 'color: #EF3E42; font-weight: bold;'
        elif col_name in ['xwOBA'] and val >= 0.380: style = 'color: #EF3E42; font-weight: bold;'
        elif col_name in ['wRC+'] and val >= 130: style = 'color: #EF3E42; font-weight: bold;'
        elif col_name == 'Whiff%' and val <= 20.0: style = 'color: #EF3E42; font-weight: bold;'
    else:
        if col_name == 'xERA' and val <= 3.30: style = 'color: #EF3E42; font-weight: bold;'
        elif col_name in ['Whiff%', 'K%'] and val >= 28.0: style = 'color: #EF3E42; font-weight: bold;'
        elif col_name == 'HardHit%' and val <= 33.0: style = 'color: #EF3E42; font-weight: bold;'
    return style

def style_grade(val):
    if not isinstance(val, str): return ''
    for grade, key in grade_to_key.items():
        if val == grade:
            bg_col = st.session_state.get(f"color_{key}", "#000")
            txt_col = "black" if grade in ['S', 'A++'] else "white"
            return f'background-color: {bg_col}; color: {txt_col}; font-weight: bold;'
    return ''

# --- 2. API 數據對接模組 ---
@st.cache_data(ttl=1800)
def fetch_daily_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    try:
        res = requests.get(url, timeout=10).json()
        if not res.get('dates'): return []
        schedule = []
        for g in res['dates'][0].get('games', []):
            away_team = g['teams']['away']['team']['name']
            home_team = g['teams']['home']['team']['name']
            away_p = g['teams']['away'].get('probablePitcher', {})
            home_p = g['teams']['home'].get('probablePitcher', {})
            schedule.append({
                'matchup': f"{away_team} @ {home_team}",
                'away_team': away_team, 'home_team': home_team,
                'away_pitcher': away_p.get('fullName', 'TBD'), 'away_pitcher_id': away_p.get('id', None),
                'home_pitcher': home_p.get('fullName', 'TBD'), 'home_pitcher_id': home_p.get('id', None)
            })
        return schedule
    except: return []

@st.cache_data(ttl=3600)
def fetch_bvp_data(pitcher_id, batter_ids):
    valid_b_ids = [str(int(b)) for b in batter_ids if pd.notna(b)]
    if not pitcher_id or not valid_b_ids: return pd.DataFrame()
    url = f"https://statsapi.mlb.com/api/v1/stats?stats=batterVsPitcher&pitcherId={int(pitcher_id)}&batterId={','.join(valid_b_ids)}"
    try:
        splits = requests.get(url, timeout=10).json().get('stats', [{}])[0].get('splits', [])
        data = []
        for s in splits:
            stat = s.get('stat', {})
            data.append({
                '打者 (Batter)': s.get('batter', {}).get('fullName', 'Unknown'),
                '打數 (AB)': stat.get('atBats', 0), '安打 (H)': stat.get('hits', 0),
                '全壘打 (HR)': stat.get('homeRuns', 0), '三振 (K)': stat.get('strikeOuts', 0),
                '保送 (BB)': stat.get('baseOnBalls', 0),
                'AVG': safe_float(stat.get('avg', 0.0)), 'OPS': safe_float(stat.get('ops', 0.0))
            })
        return pd.DataFrame(data).sort_values(by='OPS', ascending=False) if data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*24)
def fetch_historical_positions():
    pos_counts = {}
    for y in range(2016, 2027):
        url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=fielding&season={y}&playerPool=ALL"
        try:
            res = requests.get(url, timeout=10).json()
            if 'stats' in res and len(res['stats']) > 0:
                for s in res['stats'][0].get('splits', []):
                    raw_name = s.get('player', {}).get('fullName', '')
                    if not raw_name: continue
                    name_key = clean_name(raw_name)
                    pos = s.get('position', {}).get('abbreviation', 'Unknown')
                    if pos in ['P', 'PH', 'PR', 'Unknown', 'DH', 'TWP']: continue
                    games = s.get('stat', {}).get('gamesPlayed', 0)
                    if name_key not in pos_counts: pos_counts[name_key] = {}
                    pos_counts[name_key][pos] = pos_counts[name_key].get(pos, 0) + games
        except: continue
    return {nk: [p for p, g in pos.items() if g >= 50] for nk, pos in pos_counts.items() if [p for p, g in pos.items() if g >= 50]}

@st.cache_data(ttl=3600)
def process_combined_data(p_type, year, min_filter):
    group = 'pitching' if p_type == '投手' else 'hitting'
    url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group={group}&season={year}&playerPool=ALL&limit=2000&hydrate=person"
    try:
        splits = requests.get(url, timeout=15).json().get('stats', [{}])[0].get('splits', [])
        mlb_df = pd.DataFrame([s.get('stat', {}) for s in splits])
        mlb_df['Player'] = [s.get('player', {}).get('fullName', 'Unknown') for s in splits]
        mlb_df['Player_ID'] = [s.get('player', {}).get('id', None) for s in splits]
        mlb_df['Position_raw'] = [s.get('player', {}).get('primaryPosition', {}).get('abbreviation', 'Unknown') for s in splits]
        mlb_df['Team'] = [s.get('team', {}).get('name', 'Unknown') for s in splits]
    except: return pd.DataFrame()
    
    try:
        api = statcast_pitcher_expected_stats if p_type == "投手" else statcast_batter_expected_stats
        savant_df = api(year, minPA=1).reset_index()
        savant_df['Player'] = savant_df['last_name, first_name'].apply(lambda x: f"{x.split(', ')[1].strip()} {x.split(', ')[0].strip()}" if ',' in str(x) else x)
    except: savant_df = pd.DataFrame()
        
    try:
        ev_api = statcast_pitcher_exitvelo_barrels if p_type == "投手" else statcast_batter_exitvelo_barrels
        ev_df = ev_api(year, minBBE=1).reset_index()
        ev_df['Player'] = ev_df['last_name, first_name'].apply(lambda x: f"{x.split(', ')[1].strip()} {x.split(', ')[0].strip()}" if ',' in str(x) else x)
        ev_df = ev_df[['Player', 'brl_percent', 'ev95percent']]
    except: ev_df = pd.DataFrame(columns=['Player', 'brl_percent', 'ev95percent'])
    
    if mlb_df.empty or savant_df.empty: return pd.DataFrame()
    
    overlap1 = set(mlb_df.columns).intersection(set(savant_df.columns)) - {'Player'}
    savant_df = savant_df.drop(columns=list(overlap1))
    df = pd.merge(mlb_df, savant_df, on='Player', how='inner')
    
    overlap2 = set(df.columns).intersection(set(ev_df.columns)) - {'Player'}
    ev_df = ev_df.drop(columns=list(overlap2))
    df = pd.merge(df, ev_df, on='Player', how='left').fillna(0)
    
    for col in df.columns:
        if col not in ['Player', 'Player_ID', 'Position_raw', 'Team']: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    total_outs = df.get('groundOuts', 0) + df.get('airOuts', 0)
    df['GB%'] = ((df.get('groundOuts', 0) / total_outs.replace(0, 1)) * 100).fillna(0)
    
    if p_type == "打者":
        if 'plateAppearances' in df.columns: df = df[df['plateAppearances'] >= min_filter].copy()
        hist_pos = fetch_historical_positions()
        df['Position'] = df.apply(lambda row: ", ".join(hist_pos.get(clean_name(row['Player']), [row.get('Position_raw', 'DH')])), axis=1)
        
        df.rename(columns={'plateAppearances': 'PA', 'atBats': 'AB', 'runs': 'R', 'hits': 'H', 'rbi': 'RBI', 'avg': 'AVG', 'ops': 'OPS', 'obp': 'OBP', 'homeRuns': 'HR', 'stolenBases': 'SB', 'baseOnBalls': 'BB', 'strikeOuts': 'K', 'est_ba': 'xBA', 'xba': 'xBA', 'est_woba': 'xwOBA', 'xwoba': 'xwOBA', 'woba': 'wOBA', 'brl_percent': 'Barrel%', 'ev95percent': 'HardHit%'}, inplace=True)
        
        for col in ['PA', 'AB', 'R', 'H', 'RBI', 'K', 'BB', 'SB', 'HR', 'wOBA', 'xwOBA', 'wRC+', 'OPS']:
            if col not in df.columns: df[col] = 0.0
            
        pa_safe = df['PA'].replace(0, 1)
        df['K%'] = (df['K'] / pa_safe) * 100
        df['Whiff%'] = df['K%'] * 1.15
        df['wRC+'] = (df['wOBA'] / 0.320) * 100
        df['Chase%'] = 28.5 - (df['xwOBA'] * 10)
        df['WAR'] = (((df['wRC+'] - 100) * df['PA'] / 8000) + (df['SB'] * 0.04) + (df['PA'] * 0.002)).round(2)
        keep = ['Player', 'Player_ID', 'Team', 'Position', 'PA', 'AB', 'R', 'H', 'RBI', 'AVG', 'OPS', 'OBP', 'wOBA', 'HR', 'SB', 'BB', 'K', 'wRC+', 'xwOBA', 'xBA', 'HardHit%', 'Barrel%', 'Chase%', 'Whiff%', 'GB%', 'WAR']
    else:
        df['Position'] = df.apply(lambda r: 'SP' if r.get('gamesStarted', 0) > (r.get('gamesPlayed', 0) / 2) else ('CL' if r.get('saves', 0) >= 5 else 'RP'), axis=1)
        if 'inningsPitched' in df.columns:
            df['IP_calc'] = df['inningsPitched'].astype(str).str.replace('.1', '.333').str.replace('.2', '.667').astype(float)
        else:
            df['IP_calc'] = 0.0
            
        df = df[df['IP_calc'] >= min_filter].copy()
        df.rename(columns={'inningsPitched': 'IP', 'hits': 'H', 'runs': 'R', 'earnedRuns': 'ER', 'baseOnBalls': 'BB', 'strikeOuts': 'K', 'numberOfPitches': 'PC', 'homeRuns': 'HR', 'era': 'ERA', 'est_era': 'xERA', 'xera': 'xERA', 'whip': 'WHIP', 'avg': 'BA', 'est_ba': 'xBA', 'xba': 'xBA', 'est_woba': 'xwOBA', 'xwoba': 'xwOBA', 'battersFaced': 'PA_calc', 'brl_percent': 'Barrel%', 'ev95percent': 'HardHit%'}, inplace=True)
        
        for col in ['K', 'PA_calc', 'BB', 'HR', 'xBA', 'BA', 'FIP', 'ERA', 'xERA', 'WHIP', 'IP_calc', 'H', 'R', 'ER', 'PC']:
            if col not in df.columns: df[col] = 0.0
            
        pa_safe = df['PA_calc'].replace(0, 1)
        ip_safe = df['IP_calc'].replace(0, 1)
        
        df['K%'] = (df['K'] / pa_safe) * 100
        df['Whiff%'] = df['K%'] * 1.15
        df['BB%'] = (df['BB'] / pa_safe) * 100
        df['FIP'] = ((13 * df['HR']) + (3 * df['BB']) - (2 * df['K'])) / ip_safe + 3.20
        df['Diff'] = df['xBA'] - df['BA']
        raa = (4.20 - df['FIP']) * df['IP_calc'] / 9
        df['WAR'] = ((raa / 10) + (df['IP_calc'] * 0.008)).round(2)
        keep = ['Player', 'Player_ID', 'Team', 'Position', 'IP', 'H', 'R', 'ER', 'BB', 'K', 'PC', 'HR', 'ERA', 'xERA', 'WHIP', 'K%', 'BB%', 'FIP', 'BA', 'xBA', 'Diff', 'HardHit%', 'Barrel%', 'Whiff%', 'GB%', 'WAR']

    for c in keep:
        if c not in df.columns: df[c] = 0.0
    return df[keep].round(3)

@st.cache_data(ttl=3600*24*7)
def fetch_milb_mapping():
    mapping = {}
    try:
        res = requests.get("https://statsapi.mlb.com/api/v1/teams?sportIds=11,12,13,14", timeout=15).json()
        for t in res.get('teams', []):
            milb_name = t.get('name')
            parent_name = t.get('parentOrgName')
            if milb_name and parent_name:
                mapping[milb_name] = parent_name
    except: pass
    return mapping

@st.cache_data(ttl=3600*24)
def fetch_player_handedness(player_id):
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}"
        res = requests.get(url, timeout=5).json()
        person = res.get('people', [{}])[0]
        bat = person.get('batSide', {}).get('code', '-')
        pit = person.get('pitchHand', {}).get('code', '-')
        return f"Bats/Throws: {bat}/{pit}"
    except:
        return "Bats/Throws: -/-"

@st.cache_data(ttl=3600*24)
def fetch_player_career(player_id, p_type):
    group = 'hitting' if p_type == '打者' else 'pitching'
    url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}/stats?stats=yearByYear&group={group}"
    try:
        splits = requests.get(url, timeout=10).json().get('stats', [{}])[0].get('splits', [])
        data = []
        for s in splits:
            year = s.get('season', '')
            stat = s.get('stat', {})
            team = s.get('team', {}).get('name', 'Total') 
            if p_type == '打者':
                data.append({
                    'Season': year, 'Team': team,
                    'AVG': safe_float(stat.get('avg', 0)),
                    'OBP': safe_float(stat.get('obp', 0)),
                    'SLG': safe_float(stat.get('slg', 0)),
                    'OPS': safe_float(stat.get('ops', 0)),
                    'HR': int(stat.get('homeRuns', 0)),
                    'SB': int(stat.get('stolenBases', 0)),
                    'PA': int(stat.get('plateAppearances', 0)),
                    'H': int(stat.get('hits', 0))
                })
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                ip_calc = float(ip_str.replace('.1', '.333').replace('.2', '.667'))
                data.append({
                    'Season': year, 'Team': team,
                    'ERA': safe_float(stat.get('era', 0)),
                    'WHIP': safe_float(stat.get('whip', 0)),
                    'K': int(stat.get('strikeOuts', 0)),
                    'BB': int(stat.get('baseOnBalls', 0)),
                    'IP': ip_calc,
                    'W': int(stat.get('wins', 0)),
                    'L': int(stat.get('losses', 0)),
                    'SV': int(stat.get('saves', 0))
                })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.drop_duplicates(subset=['Season'], keep='last')
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_player_gamelog(player_id, p_type, year):
    group = 'hitting' if p_type == '打者' else 'pitching'
    url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}/stats?stats=gameLog&group={group}&season={year}"
    try:
        res = requests.get(url, timeout=10).json()
        splits = res.get('stats', [{}])[0].get('splits', [])
        data = []
        for s in splits:
            stat = s.get('stat', {})
            date = s.get('date', '')
            opp = s.get('opponent', {}).get('name', 'Unknown')
            is_home_game = s.get('isHome', False)
            venue_str = "🏠 主場" if is_home_game else "✈️ 客場"
            
            if p_type == '打者':
                data.append({
                    'Date': date, 'Opponent': opp, '主/客': venue_str,
                    'AVG (賽季打擊率走勢)': safe_float(stat.get('avg', 0)),
                    'OBP (賽季上壘率走勢)': safe_float(stat.get('obp', 0)),
                    'SLG (賽季長打率走勢)': safe_float(stat.get('slg', 0)),
                    'OPS (賽季OPS走勢)': safe_float(stat.get('ops', 0)),
                    'AB': int(stat.get('atBats', 0)), 'R': int(stat.get('runs', 0)),
                    'H': int(stat.get('hits', 0)), 'RBI': int(stat.get('rbi', 0)),
                    'HR': int(stat.get('homeRuns', 0)), 'SB': int(stat.get('stolenBases', 0)),
                    'BB': int(stat.get('baseOnBalls', 0)), 'K': int(stat.get('strikeOuts', 0))
                })
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                ip_calc = float(ip_str.replace('.1', '.333').replace('.2', '.667'))
                data.append({
                    'Date': date, 'Opponent': opp, '主/客': venue_str,
                    'ERA (賽季防禦率走勢)': safe_float(stat.get('era', 0)),
                    'WHIP (賽季WHIP走勢)': safe_float(stat.get('whip', 0)),
                    'IP': ip_str, 'IP_calc': ip_calc, 'H': int(stat.get('hits', 0)),
                    'R': int(stat.get('runs', 0)), 'ER': int(stat.get('earnedRuns', 0)),
                    'BB': int(stat.get('baseOnBalls', 0)), 'K': int(stat.get('strikeOuts', 0)),
                    'PC': int(stat.get('numberOfPitches', 0)), 'HR': int(stat.get('homeRuns', 0)),
                    'BF': int(stat.get('battersFaced', 0))
                })
        return pd.DataFrame(data).iloc[::-1].reset_index(drop=True) if data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*6)
def fetch_bullpen_usage(team_name, target_date_str):
    team_id = MLB_TEAM_IDS.get(team_name)
    if not team_id: return 0
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    start_date = (target_date - timedelta(days=2)).strftime("%Y-%m-%d")
    end_date = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
    
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={end_date}"
    try:
        res = requests.get(schedule_url, timeout=5).json()
        total_bp_pitches = 0
        for date_data in res.get('dates', []):
            for game in date_data.get('games', []):
                game_pk = game['gamePk']
                box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                box_res = requests.get(box_url, timeout=5).json()
                is_home = game['teams']['home']['team']['id'] == team_id
                team_side = 'home' if is_home else 'away'
                pitchers = box_res['teams'][team_side].get('pitchers', [])
                if len(pitchers) > 1:
                    for pid in pitchers[1:]:
                        player_key = f"ID{pid}"
                        p_stats = box_res['teams'][team_side]['players'].get(player_key, {}).get('stats', {}).get('pitching', {})
                        total_bp_pitches += p_stats.get('numberOfPitches', 0)
        return total_bp_pitches
    except: return 0

@st.cache_data(ttl=3600*12)
def fetch_player_home_away_splits(player_id, p_type, year):
    group = 'hitting' if p_type == '打者' else 'pitching'
    url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}/stats?stats=homeAndAway&group={group}&season={year}"
    try:
        res = requests.get(url, timeout=10).json()
        splits = res.get('stats', [{}])[0].get('splits', [])
        data = []
        for idx, s in enumerate(splits):
            is_home_val = s.get('isHome')
            if is_home_val is True:
                venue_str = "🏠 主場 (Home)"
            elif is_home_val is False:
                venue_str = "✈️ 客場 (Away)"
            else:
                venue_str = "🏠 主場 (Home)" if idx == 0 else "✈️ 客場 (Away)"
                
            stat = s.get('stat', {})
            if p_type == '打者':
                data.append({
                    '場地 (Split)': venue_str, 'PA': stat.get('plateAppearances', 0),
                    'AVG': safe_float(stat.get('avg', 0)), 'OBP': safe_float(stat.get('obp', 0)),
                    'SLG': safe_float(stat.get('slg', 0)), 'OPS': safe_float(stat.get('ops', 0)),
                    'HR': int(stat.get('homeRuns', 0)), 'K': int(stat.get('strikeOuts', 0)), 'BB': int(stat.get('baseOnBalls', 0))
                })
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                ip_calc = float(ip_str.replace('.1', '.333').replace('.2', '.667'))
                data.append({
                    '場地 (Split)': venue_str, 'IP': ip_calc, 'ERA': safe_float(stat.get('era', 0)),
                    'WHIP': safe_float(stat.get('whip', 0)), 'K': int(stat.get('strikeOuts', 0)),
                    'BB': int(stat.get('baseOnBalls', 0)), 'HR': int(stat.get('homeRuns', 0)), 'BAA': safe_float(stat.get('avg', 0))
                })
        return pd.DataFrame(data).sort_values(by='場地 (Split)', ascending=False).reset_index(drop=True)
    except: return pd.DataFrame()

# 🌟 補回缺失的 Savant Platoon 爬蟲引擎
@st.cache_data(ttl=3600*12)
def fetch_savant_platoon_splits(player_id, p_type, year):
    start_dt = f"{year}-03-01"
    end_dt = f"{year}-11-30"
    try:
        if p_type == '打者':
            df = statcast_batter(start_dt, end_dt, player_id)
            split_col = 'p_throws'
            split_map = {'L': 'vs 左投 (vs LHP)', 'R': 'vs 右投 (vs RHP)'}
        else:
            df = statcast_pitcher(start_dt, end_dt, player_id)
            split_col = 'stand'
            split_map = {'L': 'vs 左打 (vs LHB)', 'R': 'vs 右打 (vs RHB)'}
            
        if df is None or df.empty: return pd.DataFrame()
        
        pa_df = df[df['events'].notna() & (df['events'] != '')].copy()
        
        splits_data = []
        for hand in ['L', 'R']:
            hand_df = df[df[split_col] == hand]
            hand_pa = pa_df[pa_df[split_col] == hand]
            
            pa_count = len(hand_pa)
            if pa_count == 0: continue
            
            events = hand_pa['events']
            hits = events.isin(['single', 'double', 'triple', 'home_run']).sum()
            ab_events = ['single', 'double', 'triple', 'home_run', 'strikeout', 'strikeout_double_play', 'field_out', 'force_out', 'grounded_into_dp', 'double_play', 'field_error', 'fielders_choice', 'fielders_choice_out', 'other_out', 'batter_interference']
            ab_count = events.isin(ab_events).sum()
            bb_count = events.isin(['walk', 'intent_walk']).sum()
            hbp_count = events.isin(['hit_by_pitch']).sum()
            sf_count = events.isin(['sac_fly', 'sac_fly_double_play']).sum()
            k_count = events.isin(['strikeout', 'strikeout_double_play']).sum()
            hr_count = events.isin(['home_run']).sum()
            
            avg = hits / ab_count if ab_count > 0 else 0
            obp = (hits + bb_count + hbp_count) / (ab_count + bb_count + hbp_count + sf_count) if (ab_count + bb_count + hbp_count + sf_count) > 0 else 0
            tb = (events == 'single').sum() + (events == 'double').sum() * 2 + (events == 'triple').sum() * 3 + hr_count * 4
            slg = tb / ab_count if ab_count > 0 else 0
            ops = obp + slg
            
            swings = hand_df[hand_df['description'].isin(['swinging_strike', 'swinging_strike_blocked', 'foul_tip', 'hit_into_play', 'foul', 'foul_bunt', 'missed_bunt'])]
            whiffs = hand_df[hand_df['description'].isin(['swinging_strike', 'swinging_strike_blocked', 'missed_bunt'])]
            whiff_pct = (len(whiffs) / len(swings)) * 100 if len(swings) > 0 else 0
            
            bbe_df = hand_df[hand_df['type'] == 'X'].dropna(subset=['launch_speed'])
            bbe_count = len(bbe_df)
            hard_hits = len(bbe_df[bbe_df['launch_speed'] >= 95.0])
            hard_hit_pct = (hard_hits / bbe_count) * 100 if bbe_count > 0 else 0
            
            barrels = len(bbe_df[bbe_df['launch_speed_angle'] == 6.0]) 
            barrel_pct = (barrels / bbe_count) * 100 if bbe_count > 0 else 0
            
            avg_ev = bbe_df['launch_speed'].mean() if bbe_count > 0 else 0
            
            splits_data.append({
                '對戰慣用手 (Split)': split_map[hand],
                'PA': pa_count,
                'AVG': safe_float(avg),
                'OBP': safe_float(obp),
                'SLG': safe_float(slg),
                'OPS': safe_float(ops),
                'K%': safe_float((k_count / pa_count) * 100),
                'BB%': safe_float((bb_count / pa_count) * 100),
                'HardHit%': safe_float(hard_hit_pct),
                'Barrel%': safe_float(barrel_pct),
                'Whiff%': safe_float(whiff_pct),
                'Avg EV': safe_float(avg_ev)
            })
            
        res_df = pd.DataFrame(splits_data)
        return res_df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600*24)
def fetch_milb_stats(year, sid, p_type):
    group = 'hitting' if p_type == '打者' else 'pitching'
    mapping = fetch_milb_mapping()
    try:
        url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group={group}&season={year}&playerPool=ALL&sportId={sid}&limit=5000"
        splits = requests.get(url, timeout=15).json().get('stats', [{}])[0].get('splits', [])
        data = []
        for s in splits:
            stat = s.get('stat', {})
            milb_team = s.get('team', {}).get('name', 'Unknown')
            mlb_team = mapping.get(milb_team, milb_team) 
            player_name = s['player']['fullName']
            if p_type == '打者':
                pa = stat.get('plateAppearances', 0)
                if pa >= 50:
                    data.append({
                        '球員 (Player)': player_name, '大聯盟母隊 (MLB Team)': mlb_team, 'PA': pa,
                        'H': stat.get('hits', 0), 'HR': stat.get('homeRuns', 0), 'SB': stat.get('stolenBases', 0),
                        'AVG': float(stat.get('avg', 0)), 'OBP': float(stat.get('obp', 0)),
                        'SLG': float(stat.get('slg', 0)), 'OPS': float(stat.get('ops', 0))
                    })
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                ip_calc = float(ip_str.replace('.1', '.333').replace('.2', '.667'))
                if ip_calc >= 20.0:
                    data.append({
                        '球員 (Player)': player_name, '大聯盟母隊 (MLB Team)': mlb_team, 'IP': ip_str,
                        'W': stat.get('wins', 0), 'L': stat.get('losses', 0), 'ERA': float(stat.get('era', 0)),
                        'WHIP': float(stat.get('whip', 0)), 'K': stat.get('strikeOuts', 0), 'BB': stat.get('baseOnBalls', 0)
                    })
        return pd.DataFrame(data)
    except: return pd.DataFrame()

# --- 4. 側欄功能區 ---
with st.sidebar:
    tw_tz = timezone(timedelta(hours=8))
    year = datetime.now(tw_tz).year 
    p_type = st.radio("球員類型 (切換分頁動態配置)", ["打者", "投手"])
    min_filter = st.number_input("設定本季 PA (打席) 下限", min_value=0, value=100, step=50) if p_type == "打者" else st.number_input("設定本季 IP (投球局數) 下限", min_value=0.0, value=30.0, step=5.0)
    
    data = process_combined_data(p_type, year, min_filter).copy()
    
    if not data.empty:
        all_players = sorted(data['Player'].unique().tolist())
        search_players = st.multiselect("🔍 全局球員快搜 (支援下拉選單與打字)", all_players)
        if search_players:
            data = data[data['Player'].isin(search_players)]
            
        st.markdown("---")
        pos_list = sorted(list(set(p for sub in data['Position'].dropna().str.split(', ') for p in sub))) if p_type == "打者" else sorted(data['Position'].unique().tolist())
        selected_pos = st.multiselect("🛡️ 篩選守備位置 / 角色", pos_list, default=pos_list)
        if selected_pos: 
            data = data[data['Position'].apply(lambda x: any(p in x.split(', ') for p in selected_pos))] if p_type == "打者" else data[data['Position'].isin(selected_pos)]
                
        if not data.empty:
            exclude = ['Player', 'Player_ID', 'Team', 'Position', 'PA', 'AB', 'R', 'ER', 'PC', 'IP', 'H', 'HR', 'SB', 'Diff']
            metrics = [c for c in data.columns if c not in exclude]
            scores = [round(sum(get_relative_grade(data, m, row[m], p_type)[1] for m in metrics)/len(metrics), 3) for _, row in data.iterrows()]
            data['綜合分數'] = scores
            data = data.sort_values(by='綜合分數', ascending=False).reset_index(drop=True)
            data.insert(0, '同池排名', data.index + 1)
            data.insert(1, '綜合評級', data['綜合分數'].apply(score_to_grade))
            data = data.drop(columns=['綜合分數'])
            
            st.markdown("🎯 **交叉雷達圖與對決專用目標**")
            target1 = st.selectbox("雷達圖主要目標", data['Player'].unique(), key='t1')
            target2 = st.selectbox("對決評比對象", data['Player'].unique(), key='t2')
            default_metrics = metrics[:5]
            if 'WAR' in metrics and 'WAR' not in default_metrics: default_metrics[-1] = 'WAR'
            selected_metrics = st.multiselect("雷達圖顯示指標", metrics, default=default_metrics)

    st.markdown("---")
    with st.expander("⚙️ 系統外觀設定"):
        st.session_state.font_size = st.slider("📄 全局介面字體大小 (px)", min_value=12, max_value=30, value=st.session_state.font_size, step=1)
        st.session_state.table_font_size = st.slider("📊 數據表格專用字體 (px)", min_value=10, max_value=24, value=st.session_state.table_font_size, step=1)
        
        st.markdown("**🌟 11 階評級顏色自訂**")
        c1, c2, c3, c4 = st.columns(4)
        st.session_state.color_S = c1.color_picker("S", st.session_state.color_S)
        st.session_state.color_A_plus_plus = c2.color_picker("A++", st.session_state.color_A_plus_plus)
        st.session_state.color_A_plus = c3.color_picker("A+", st.session_state.color_A_plus)
        st.session_state.color_A = c4.color_picker("A", st.session_state.color_A)
        c5, c6, c7, c8 = st.columns(4)
        st.session_state.color_B_plus_plus = c5.color_picker("B++", st.session_state.color_B_plus_plus)
        st.session_state.color_B_plus = c6.color_picker("B+", st.session_state.color_B_plus)
        st.session_state.color_B = c7.color_picker("B", st.session_state.color_B)
        st.session_state.color_C = c8.color_picker("C", st.session_state.color_C)
        c9, c10, c11, _ = st.columns(4)
        st.session_state.color_D = c9.color_picker("D", st.session_state.color_D)
        st.session_state.color_E = c10.color_picker("E", st.session_state.color_E)
        st.session_state.color_F = c11.color_picker("F", st.session_state.color_F)

# 🌟 全域動態環境佈局
if not data.empty:
    default_player = data['Player'].iloc[0]
    profile_target = st.session_state.get('prof_target', default_player)
    if profile_target not in data['Player'].values: profile_target = default_player
    p_prof = data[data['Player'] == profile_target].iloc[0]
    p_prof_color = get_team_color(p_prof['Team'])[0]

    logo_url = get_team_logo_url(p_prof['Team'])
    logo_html = f"<img src='{logo_url}' width='45' style='vertical-align: middle; margin-right: 12px;'>" if logo_url else ""

    st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{ background-color: {hex_to_rgba(p_prof_color, 0.08)} !important; transition: background-color 0.5s ease; }}
        .stApp {{ background-color: {hex_to_rgba(p_prof_color, 0.08)} !important; transition: background-color 0.5s ease; }}
        [data-testid="stHeader"] {{ background-color: transparent !important; }}
        
        [data-testid="stMetricDelta"] > div {{ font-size: 1.15rem !important; font-weight: 900 !important; }}
        [data-testid="stMetricDelta"] svg {{ width: 1.8rem !important; height: 1.8rem !important; }}
        [data-testid="stMetricDelta"] {{ filter: brightness(1.25) saturate(1.6); }}
        
        .block-container {{ max-width: 1400px !important; margin: 0 auto !important; padding-top: 2rem !important; padding-bottom: 2rem !important; }}
        .table-scroll-container {{ width: 100%; max-height: 65vh; overflow: auto; border: 1px solid #e0e0e0; border-radius: 8px; background-color: white; margin-bottom: 20px; }}
        table.dataframe {{ width: 100%; border-collapse: collapse; margin: 0; background-color: white; }}
        table.dataframe th, table.dataframe td {{ padding: 6px 12px; border: 1px solid #e0e0e0; text-align: center !important; white-space: nowrap; font-size: {st.session_state.table_font_size}px !important; }}
        table.dataframe thead th {{ background-color: {p_prof_color}; color: white !important; font-size: {max(10, st.session_state.table_font_size - 1)}px !important; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 2px -1px rgba(0,0,0,0.4); }}
        
        button[data-baseweb="tab"] p {{ font-size: {max(12, st.session_state.font_size - 1)}px !important; font-weight: bold; }}
        [data-testid="stSidebar"] {{ background-color: {hex_to_rgba(p_prof_color, 0.82)} !important; transition: background-color 0.5s ease; }}
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] span {{ color: white !important; }}
        [data-testid="stSidebar"] input, [data-testid="stSidebar"] div[data-baseweb="select"] * {{ color: #31333F !important; }}
        </style>
    """, unsafe_allow_html=True)

# --- 6. 主顯示區 ---
if not data.empty:
    p1, p2 = data[data['Player'] == target1].iloc[0], data[data['Player'] == target2].iloc[0]
    t1_colors, t2_colors = get_team_color(p1['Team']), get_team_color(p2['Team'])
    p1_color = t1_colors[0]
    p2_color = t2_colors[0] if t2_colors[0] != p1_color else t2_colors[1]
    
    if p_type == "打者":
        tab_profile, tab_rank, tab_radar, tab_scatter, tab_h2h, tab_predict, tab_mvp, tab_milb = st.tabs(["🔍 專屬面版", "📊 排名", "📈 雷達", "🌌 散佈", "⚖️ 對決", "🔮 預測", "👑 MVP", "🌱 MiLB"])
        tab_cy = None
    else:
        tab_profile, tab_rank, tab_radar, tab_scatter, tab_h2h, tab_predict, tab_mvp, tab_cy, tab_milb = st.tabs(["🔍 專屬面版", "📊 排名", "📈 雷達", "🌌 散佈", "⚖️ 對決", "🔮 預測", "👑 MVP", "🏆 賽揚", "🌱 MiLB"])
    
    with tab_profile:
        col_prof_search, _ = st.columns([1, 2])
        col_prof_search.selectbox("🔍 選擇要查看的球員", data['Player'].unique(), index=list(data['Player'].unique()).index(profile_target), key='prof_target')
        
        hand_info = fetch_player_handedness(p_prof['Player_ID'])
        st.markdown(f"<h2 style='color:{p_prof_color}; border-bottom: 3px solid {p_prof_color}; padding-bottom: 10px; transition: border-color 0.5s ease; display: flex; align-items: center;'>{logo_html} <span> {profile_target} <span style='font-size:0.6em; color:#A5ACAF;'>({hand_info})</span> | {p_prof['Team']} - {p_prof['Position']}</span></h2>", unsafe_allow_html=True)
        
        st.markdown("### 📊 本賽季核心數據與最新動態 (Season Stats & Trends)")
        
        gamelog_df = fetch_player_gamelog(int(p_prof['Player_ID']), p_type, year)
        last_game = gamelog_df.iloc[0] if not gamelog_df.empty else None
        prev_game = gamelog_df.iloc[1] if len(gamelog_df) > 1 else None
        
        if p_type == '打者':
            m_cols = st.columns(9)
            m_cols[0].metric("AB", int(p_prof['AB']), delta=f"+{int(last_game['AB'])}" if last_game is not None and last_game['AB']>0 else None, delta_color="normal")
            m_cols[1].metric("R", int(p_prof['R']), delta=f"+{int(last_game['R'])}" if last_game is not None and last_game['R']>0 else None, delta_color="normal")
            m_cols[2].metric("H", int(p_prof['H']), delta=f"+{int(last_game['H'])}" if last_game is not None and last_game['H']>0 else None, delta_color="normal")
            m_cols[3].metric("RBI", int(p_prof['RBI']), delta=f"+{int(last_game['RBI'])}" if last_game is not None and last_game['RBI']>0 else None, delta_color="normal")
            m_cols[4].metric("HR", int(p_prof['HR']), delta=f"+{int(last_game['HR'])}" if last_game is not None and last_game['HR']>0 else None, delta_color="normal")
            m_cols[5].metric("SB", int(p_prof['SB']), delta=f"+{int(last_game['SB'])}" if last_game is not None and last_game['SB']>0 else None, delta_color="normal")
            m_cols[6].metric("BB", int(p_prof['BB']), delta=f"+{int(last_game['BB'])}" if last_game is not None and last_game['BB']>0 else None, delta_color="normal")
            m_cols[7].metric("K", int(p_prof['K']), delta=f"+{int(last_game['K'])}" if last_game is not None and last_game['K']>0 else None, delta_color="inverse")
            d_avg = round(last_game['AVG (賽季打擊率走勢)'] - prev_game['AVG (賽季打擊率走勢)'], 3) if prev_game is not None else 0.0
            m_cols[8].metric("AVG", f"{p_prof['AVG']:.3f}", delta=f"{d_avg:.3f}" if d_avg != 0 else None, delta_color="normal")
        else:
            m_cols = st.columns(10)
            m_cols[0].metric("IP", p_prof['IP'], delta=f"+{last_game['IP']}" if last_game is not None and last_game['IP_calc']>0 else None, delta_color="normal")
            m_cols[1].metric("H", int(p_prof['H']), delta=f"+{int(last_game['H'])}" if last_game is not None and last_game['H']>0 else None, delta_color="inverse")
            m_cols[2].metric("R", int(p_prof['R']), delta=f"+{int(last_game['R'])}" if last_game is not None and last_game['R']>0 else None, delta_color="inverse")
            m_cols[3].metric("ER", int(p_prof['ER']), delta=f"+{int(last_game['ER'])}" if last_game is not None and last_game['ER']>0 else None, delta_color="inverse")
            m_cols[4].metric("BB", int(p_prof['BB']), delta=f"+{int(last_game['BB'])}" if last_game is not None and last_game['BB']>0 else None, delta_color="inverse")
            m_cols[5].metric("K", int(p_prof['K']), delta=f"+{int(last_game['K'])}" if last_game is not None and last_game['K']>0 else None, delta_color="normal")
            m_cols[6].metric("PC", int(p_prof['PC']), delta=f"+{int(last_game['PC'])}" if last_game is not None and last_game['PC']>0 else None, delta_color="off")
            m_cols[7].metric("HR", int(p_prof['HR']), delta=f"+{int(last_game['HR'])}" if last_game is not None and last_game['HR']>0 else None, delta_color="inverse")
            d_whip = round(last_game['WHIP (賽季WHIP走勢)'] - prev_game['WHIP (賽季WHIP走勢)'], 3) if prev_game is not None else 0.0
            m_cols[8].metric("WHIP", f"{p_prof['WHIP']:.2f}", delta=f"{d_whip:.2f}" if d_whip != 0 else None, delta_color="inverse")
            d_era = round(last_game['ERA (賽季防禦率走勢)'] - prev_game['ERA (賽季防禦率走勢)'], 2) if prev_game is not None else 0.0
            m_cols[9].metric("ERA", f"{p_prof['ERA']:.2f}", delta=f"{d_era:.2f}" if d_era != 0 else None, delta_color="inverse")

        st.markdown("### 📅 近 5 場逐場賽事表現 (Last 5 Games Log)")
        if not gamelog_df.empty:
            recent_5 = gamelog_df.head(5).copy()
            if p_type == '打者':
                recent_5 = recent_5.rename(columns={'AVG (賽季打擊率走勢)': 'AVG'})
                show_cols = ['Date', 'Opponent', '主/客', 'AB', 'R', 'H', 'RBI', 'HR', 'SB', 'BB', 'K', 'AVG']
            else:
                recent_5 = recent_5.rename(columns={'WHIP (賽季WHIP走勢)': 'WHIP', 'ERA (賽季防禦率走勢)': 'ERA'})
                show_cols = ['Date', 'Opponent', '主/客', 'IP', 'H', 'R', 'ER', 'BB', 'K', 'PC', 'HR', 'WHIP', 'ERA']
            
            def color_gamelog_rows(row):
                is_home = "主場" in str(row['主/客'])
                if is_home:
                    bg = hex_to_rgba(p_prof_color, 0.18)
                else:
                    opp_color = get_team_color(row['Opponent'])[0]
                    bg = hex_to_rgba(opp_color, 0.18)
                return [f'background-color: {bg}; color: black; font-weight: 500;' for _ in row.index]
                
            styled_recent_5 = recent_5[show_cols].style.apply(color_gamelog_rows, axis=1).format(precision=3).hide(axis='index')
            st.markdown(f"<div class='table-scroll-container'>{styled_recent_5.to_html()}</div>", unsafe_allow_html=True)
        else:
            st.info("⚠️ 目前查無本賽季出賽紀錄。")

        st.markdown("---")
        prs = {m: get_percentile(data, m, p_prof[m], p_type) for m in metrics}
        sorted_prs = sorted(prs.items(), key=lambda x: x[1], reverse=True)
        strengths = [item for item in sorted_prs if item[1] >= 75][:4]
        weaknesses = [item for item in sorted_prs if item[1] <= 35][-4:]
        weaknesses = sorted(weaknesses, key=lambda x: x[1])
        conclusion = generate_scout_conclusion(prs, p_prof.get('WAR', 0), p_type)
        
        # 🌟 核心升級 2：垂直不並排，確保介面整潔舒適
        st.markdown("### 🤖 深度球探報告")
        st.markdown("#### 🟢 優勢 (Strengths)")
        if strengths:
            for m, pr in strengths: st.markdown(f"<span style='font-size:{st.session_state.font_size}px;'>• **{m}** 聯盟前 {max(1, 100-pr):.0f}%</span>", unsafe_allow_html=True)
        else: st.markdown(f"<span style='font-size:{st.session_state.font_size}px;'>• 無明顯頂尖數據</span>", unsafe_allow_html=True)
        
        st.markdown("#### 🔴 弱點 (Weaknesses)")
        if weaknesses:
            for m, pr in weaknesses:
                desc = "偏高" if pr > 15 else "極差"
                st.markdown(f"<span style='font-size:{st.session_state.font_size}px;'>• **{m}** {desc} (倒數 {max(1, pr):.0f}%)</span>", unsafe_allow_html=True)
        else: st.markdown(f"<span style='font-size:{st.session_state.font_size}px;'>• 無明顯數據短板</span>", unsafe_allow_html=True)
        
        st.markdown("#### 📝 總結定位")
        st.info(f"**{conclusion}** | 綜合評級: {p_prof['綜合評級']} | 同池排名: 第 {p_prof['同池排名']} 名")
            
        st.markdown("---")
        st.markdown("### 🎯 五角戰力雷達")
        res_prof = [prs.get(m, 0) for m in selected_metrics]
        fig_prof = go.Figure()
        fig_prof.add_trace(go.Scatterpolar(r=res_prof, theta=selected_metrics, fill='toself', line_color=p_prof_color, name=profile_target))
        fig_prof.update_layout(polar=dict(radialaxis=dict(range=[0, 100])), showlegend=False, margin=dict(t=20, b=20, l=20, r=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=500)
        st.plotly_chart(fig_prof, use_container_width=True, config={'scrollZoom': True})
            
        st.markdown("---")
        title_text = "### 📈 近期百打數 (100 AB) 狀態走勢圖" if p_type == '打者' else "### 📈 近期百打席 (100 BF) 狀態走勢圖"
        st.markdown(title_text)

        if not gamelog_df.empty:
            col_log_sel, _ = st.columns([1, 2])
            log_metrics = [c for c in gamelog_df.columns if '走勢' in c]
            sel_log_metric = col_log_sel.selectbox("選擇近況分析指標", log_metrics)
            
            gamelog_trend = gamelog_df.copy().iloc[::-1].reset_index(drop=True)
            accum_col = 'AB' if p_type == '打者' else 'BF'
            gamelog_trend['Cum'] = gamelog_trend[accum_col].cumsum()
            recent_df = gamelog_trend[gamelog_trend['Cum'] <= 110] 
            if len(recent_df) < 3: recent_df = gamelog_trend.head(15) 
            recent_df = recent_df.iloc[::-1].reset_index(drop=True)
            
            fig_line = go.Figure()
            lower_is_better_trend = ['ERA (賽季防禦率走勢)', 'WHIP (賽季WHIP走勢)']
            is_lower_better = sel_log_metric in lower_is_better_trend
            
            for i in range(1, len(recent_df)):
                x0, x1 = recent_df['Date'].iloc[i-1], recent_df['Date'].iloc[i]
                y0, y1 = recent_df[sel_log_metric].iloc[i-1], recent_df[sel_log_metric].iloc[i]
                
                if y1 > y0:
                    fill_color = "rgba(220, 50, 50, 0.15)" if is_lower_better else "rgba(50, 220, 50, 0.15)"
                elif y1 < y0:
                    fill_color = "rgba(50, 220, 50, 0.15)" if is_lower_better else "rgba(220, 50, 50, 0.15)"
                else:
                    fill_color = "rgba(0,0,0,0)"
                    
                fig_line.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode='lines', line=dict(width=0), fill='tozeroy', fillcolor=fill_color, showlegend=False, hoverinfo='skip'))
            
            fig_line.add_trace(go.Scatter(x=recent_df['Date'], y=recent_df[sel_log_metric], mode='lines+markers', line=dict(color=p_prof_color, width=3), marker=dict(size=8, color='white', line=dict(color=p_prof_color, width=2)), text=recent_df['Opponent'], hovertemplate="<b>日期:</b> %{x}<br><b>對手:</b> %{text}<br><b>數據:</b> %{y:.3f}<extra></extra>", showlegend=False))
            fig_line.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=400, xaxis_title="比賽日期 (Date)", yaxis_title=sel_log_metric, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_line, use_container_width=True, config={'scrollZoom': True})

        st.markdown("---")
        st.markdown("### 🌌 專屬進階數據落點")
        col_x, col_y = st.columns(2)
        plot_metrics = [c for c in data.columns if c not in ['同池排名', '綜合評級', 'Player', 'Player_ID', 'Team', 'Position']]
        def_x = plot_metrics.index('WAR') if 'WAR' in plot_metrics else 0
        def_y = plot_metrics.index('wRC+') if 'wRC+' in plot_metrics else (plot_metrics.index('Barrel%') if 'Barrel%' in plot_metrics else 1)
        x_col_prof = col_x.selectbox("指定 X 軸落點", plot_metrics, index=def_x, key='prof_x')
        y_col_prof = col_y.selectbox("指定 Y 軸落點", plot_metrics, index=def_y, key='prof_y')
        
        team_colors_map = {t: get_team_color(t)[0] for t in data['Team'].unique()}
        fig_scatter_prof = px.scatter(data, x=x_col_prof, y=y_col_prof, color="Team", hover_name="Player", color_discrete_map=team_colors_map)
        for trace in fig_scatter_prof.data: trace.showlegend = False
        fig_scatter_prof.add_scatter(x=[p_prof[x_col_prof]], y=[p_prof[y_col_prof]], mode='markers', marker=dict(size=25, color=p_prof_color, symbol='star', line=dict(color='white', width=2)), name=profile_target, showlegend=True)
        fig_scatter_prof.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=550, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_scatter_prof, use_container_width=True, config={'scrollZoom': True})

        st.markdown("---")
        st.markdown("### 📊 本季單人完整進階數據表")
        single_df = data[data['Player'] == profile_target].drop(columns=['Player_ID'], errors='ignore')
        styled_single = single_df.style.apply(lambda x: [highlight_elite_stats(v, x.name, p_type) for v in x], axis=0).map(style_grade, subset=['綜合評級']).format(precision=3).hide(axis='index')
        st.markdown(f"<div class='table-scroll-container' style='max-height: none;'>{styled_single.to_html()}</div>", unsafe_allow_html=True)
        
        # 🌟 補回缺失的 Savant Platoon UI 模組
        st.markdown("---")
        st.markdown("### ⚔️ 對決左右手數據 (Savant Platoon Splits)")
        with st.spinner("載入 Savant 進階對戰數據..."):
            platoon_df = fetch_savant_platoon_splits(p_prof['Player_ID'], p_type, year)
            if not platoon_df.empty:
                styled_platoon = platoon_df.style.format({
                    'AVG': '{:.3f}', 'OBP': '{:.3f}', 'SLG': '{:.3f}', 'OPS': '{:.3f}',
                    'K%': '{:.1f}%', 'BB%': '{:.1f}%', 'HardHit%': '{:.1f}%', 'Barrel%': '{:.1f}%', 'Whiff%': '{:.1f}%', 'Avg EV': '{:.1f}'
                }).hide(axis='index')
                st.markdown(f"<div class='table-scroll-container' style='max-height: none;'>{styled_platoon.to_html()}</div>", unsafe_allow_html=True)
            else:
                st.info("⚠️ 查無本季 Savant 進階對戰左右手數據。")
        
        st.markdown("---")
        st.markdown("### 🏟️ 主客場表現差異 (Home/Away)")
        with st.spinner("載入主客場數據..."):
            ha_df = fetch_player_home_away_splits(p_prof['Player_ID'], p_type, year)
            if not ha_df.empty:
                styled_ha = ha_df.style.format(precision=3).hide(axis='index')
                st.markdown(f"<div class='table-scroll-container' style='max-height: none;'>{styled_ha.to_html()}</div>", unsafe_allow_html=True)
            else:
                st.info("⚠️ 查無本季主客場數據。")
                
        st.markdown("---")
        st.markdown("### 📜 生涯逐年數據走勢 (Career Trend)")
        with st.spinner("載入生涯數據..."):
            career_df = fetch_player_career(p_prof['Player_ID'], p_type)
            if not career_df.empty:
                col_c_sel, _ = st.columns([1, 2])
                career_metrics = [c for c in career_df.columns if c not in ['Season', 'Team']]
                def_c_idx = career_metrics.index('OPS') if p_type == '打者' and 'OPS' in career_metrics else (career_metrics.index('ERA') if p_type == '投手' and 'ERA' in career_metrics else 0)
                sel_career_metric = col_c_sel.selectbox("選擇生涯指標", career_metrics, index=def_c_idx, key='career_metric')
                
                fig_career = px.line(career_df, x='Season', y=sel_career_metric, hover_data=['Team'], markers=True, color_discrete_sequence=[p_prof_color])
                fig_career.update_traces(marker=dict(size=10, line=dict(color='white', width=2)), line=dict(width=3))
                fig_career.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=450, xaxis_title="賽季 (Season)", yaxis_title=sel_career_metric, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_career, use_container_width=True, config={'scrollZoom': True})
            else:
                st.info("⚠️ 查無生涯逐年數據。")

    with tab_rank:
        st.markdown("### 🏆 全聯盟大數據洗牌與排名")
        col_sort1, col_sort2 = st.columns([1, 2])
        sortable_cols = [c for c in data.columns if c not in ['Player', 'Player_ID', 'Team', 'Position', '同池排名', '綜合評級']]
        def_sort_idx = sortable_cols.index('WAR') if 'WAR' in sortable_cols else 0
        sort_metric = col_sort1.selectbox("🔍 選擇重新排序指標", sortable_cols, index=def_sort_idx)
        
        if p_type == '打者': lower_is_better_metrics = ['Chase%', 'Whiff%', 'GB%', 'K%']
        else: lower_is_better_metrics = ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
        def_order_rank = 1 if sort_metric in lower_is_better_metrics else 0
        sort_order = col_sort2.radio("排序方式", ["由高到低", "由低到高"], index=def_order_rank, horizontal=True)
        
        asc = True if sort_order == "由低到高" else False
        sorted_data = data.sort_values(by=sort_metric, ascending=asc).reset_index(drop=True)
        sorted_data['同池排名'] = sorted_data.index + 1
        
        styled_df = sorted_data.drop(columns=['Player_ID'], errors='ignore').style.apply(lambda x: [highlight_elite_stats(v, x.name, p_type) for v in x], axis=0).map(style_grade, subset=['綜合評級']).format(precision=3).hide(axis='index')
        st.markdown(f"<div class='table-scroll-container'>{styled_df.to_html()}</div>", unsafe_allow_html=True)

    with tab_radar:
        res1 = [get_percentile(data, m, p1[m], p_type) for m in selected_metrics]
        res2 = [get_percentile(data, m, p2[m], p_type) for m in selected_metrics]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=res1, theta=selected_metrics, fill='toself', line_color=p1_color, name=target1))
        if target1 != target2: fig.add_trace(go.Scatterpolar(r=res2, theta=selected_metrics, fill='toself', line_color=p2_color, name=target2))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])), showlegend=True, height=650, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
        
        st.markdown("---")
        cols = st.columns(len(selected_metrics))
        for i, m in enumerate(selected_metrics):
            pr1 = get_percentile(data, m, p1[m], p_type)
            if target1 != target2:
                pr2 = get_percentile(data, m, p2[m], p_type)
                cols[i].markdown(f"<div style='font-size:{int(st.session_state.font_size * 1.6)}px;'><b>{m}</b><br><span style='color:{p1_color}; font-weight:bold;'>■ {target1}</span>: {p1[m]:.3f} (PR: {pr1})<br><span style='color:{p2_color}; font-weight:bold;'>■ {target2}</span>: {p2[m]:.3f} (PR: {pr2})</div>", unsafe_allow_html=True)
            else:
                cols[i].markdown(f"<div style='font-size:{int(st.session_state.font_size * 1.6)}px;'><b>{m}</b><br><span style='color:{p1_color}; font-weight:bold;'>■ {target1}</span>: {p1[m]:.3f} (PR: {pr1})</div>", unsafe_allow_html=True)

    with tab_scatter:
        x_col = st.selectbox("X 軸", plot_metrics, index=def_x)
        y_col = st.selectbox("Y 軸", plot_metrics, index=def_y)
        fig = px.scatter(data, x=x_col, y=y_col, color="Team", hover_name="Player", color_discrete_map=team_colors_map)
        for trace in fig.data: trace.showlegend = False
        fig.add_scatter(x=[p1[x_col]], y=[p1[y_col]], mode='markers', marker=dict(size=22, color=p1_color, symbol='star', line=dict(color='white', width=2)), name=target1, showlegend=True)
        if target1 != target2: fig.add_scatter(x=[p2[x_col]], y=[p2[y_col]], mode='markers', marker=dict(size=18, color=p2_color, symbol='star', line=dict(color='white', width=1.5)), name=target2, showlegend=True)
        fig.update_layout(height=650, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

    with tab_h2h:
        st.subheader(f"⚖️ {target1} VS {target2} (全指標生死鬥)")
        for m in metrics:
            col_m1, col_m2 = st.columns(2)
            lower_list = ['Chase%', 'Whiff%', 'GB%', 'K%'] if p_type == '打者' else ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'HardHit%', 'Barrel%', 'Diff']
            is_lower_better = m in lower_list
            v1, v2 = p1[m], p2[m]
            
            if is_lower_better: win1, win2 = v1 < v2, v2 < v1
            else: win1, win2 = v1 > v2, v2 > v1
            c1 = "#00E676" if win1 else ("#FF4444" if win2 else "#A9A9A9")
            c2 = "#00E676" if win2 else ("#FF4444" if win1 else "#A9A9A9")
            grade1, _ = get_relative_grade(data, m, v1, p_type)
            grade2, _ = get_relative_grade(data, m, v2, p_type)
            
            base_h2h_size = int(st.session_state.font_size * 1.5)
            h_size = int(st.session_state.font_size * 2.2)
            col_m1.markdown(f"<div style='font-size:{base_h2h_size}px;'><b>{target1} ({m})</b><br><span style='font-size:{h_size}px; color:{c1}; font-weight:bold;'>{v1:.3f}</span> (評級: {grade1})</div>", unsafe_allow_html=True)
            if target1 != target2: col_m2.markdown(f"<div style='font-size:{base_h2h_size}px;'><b>{target2} ({m})</b><br><span style='font-size:{h_size}px; color:{c2}; font-weight:bold;'>{v2:.3f}</span> (評級: {grade2})</div>", unsafe_allow_html=True)
            st.divider()

    with tab_predict:
        st.markdown("### 📅 賽程預測中心與勝率推算")
        col_d, col_g = st.columns([1, 2])
        target_date = col_d.date_input("選擇比賽日期", datetime.now(timezone(timedelta(hours=8))).date())
        schedule = fetch_daily_schedule(target_date.strftime("%Y-%m-%d"))
        
        selected_game = None
        if schedule:
            selected_game_str = col_g.selectbox("選擇預測賽事", [g['matchup'] for g in schedule])
            selected_game = next(g for g in schedule if g['matchup'] == selected_game_str)
        else:
            col_g.warning("該日無賽事或尚未公佈")
        
        st.markdown("---")

        if selected_game:
            away_t, home_t = selected_game['away_team'], selected_game['home_team']
            away_p, home_p = selected_game['away_pitcher'], selected_game['home_pitcher']
            away_p_id, home_p_id = selected_game['away_pitcher_id'], selected_game['home_pitcher_id']
            
            home_t_color = get_team_color(home_t)[0]
            away_t_color = get_team_color(away_t)[0]
            if home_t_color == away_t_color: away_t_color = get_team_color(away_t)[1]
            
            with st.spinner("加載預測引擎數據中..."):
                pred_hitters = process_combined_data("打者", year, 0)
                pred_pitchers = process_combined_data("投手", year, 0)
                
                hp_stats = pred_pitchers[pred_pitchers['Player'] == home_p]
                ap_stats = pred_pitchers[pred_pitchers['Player'] == away_p]
                hh_stats = pred_hitters[pred_hitters['Team'] == home_t]
                ah_stats = pred_hitters[pred_hitters['Team'] == away_t]
                
                home_rp = pred_pitchers[(pred_pitchers['Team'] == home_t) & (pred_pitchers['Position'].isin(['RP', 'CL']))]
                away_rp = pred_pitchers[(pred_pitchers['Team'] == away_t) & (pred_pitchers['Position'].isin(['RP', 'CL']))]
                
                home_bp_era = home_rp['ERA'].mean() if not home_rp.empty else 4.0
                away_bp_era = away_rp['ERA'].mean() if not away_rp.empty else 4.0
                
                home_bp_pitches = fetch_bullpen_usage(home_t, target_date.strftime("%Y-%m-%d"))
                away_bp_pitches = fetch_bullpen_usage(away_t, target_date.strftime("%Y-%m-%d"))
                
                away_ops = ah_stats['OPS'].mean() if not ah_stats.empty else 0.700
                home_ops = hh_stats['OPS'].mean() if not hh_stats.empty else 0.700
                away_p_war = ap_stats['WAR'].sum() if not ap_stats.empty else 0.0
                home_p_war = hp_stats['WAR'].sum() if not hp_stats.empty else 0.0
                away_p_era = ap_stats['ERA'].mean() if not ap_stats.empty else 4.00
                home_p_era = hp_stats['ERA'].mean() if not hp_stats.empty else 4.00
                
                away_lineup_score = away_ops * 100
                away_sp_score = max(0, 5 - away_p_era) * 10 + away_p_war * 5
                away_bp_score = max(0, 5 - away_bp_era) * 8 - (away_bp_pitches * 0.05)
                away_strength = away_lineup_score + away_sp_score + away_bp_score
                
                home_lineup_score = home_ops * 100
                home_sp_score = max(0, 5 - home_p_era) * 10 + home_p_war * 5
                home_bp_score = max(0, 5 - home_bp_era) * 8 - (home_bp_pitches * 0.05)
                home_strength = home_lineup_score + home_sp_score + home_bp_score + 3.0
                
                total_strength = away_strength + home_strength
                if total_strength == 0:
                    home_win_prob, away_win_prob = 50.0, 50.0
                else:
                    home_win_prob = (home_strength / total_strength) * 100
                    away_win_prob = (away_strength / total_strength) * 100
                
                st.subheader(f"🔮 {selected_game['matchup']} 戰力與勝率預測")
                
                st.markdown(f"""
                <div style="display: flex; height: 40px; border-radius: 8px; overflow: hidden; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="width: {away_win_prob}%; background-color: {away_t_color}; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: {int(st.session_state.font_size * 1.6)}px;">
                        {away_t} {away_win_prob:.1f}%
                    </div>
                    <div style="width: {home_win_prob}%; background-color: {home_t_color}; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: {int(st.session_state.font_size * 1.6)}px;">
                        {home_t} {home_win_prob:.1f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                reasoning = []
                if home_p_era < away_p_era:
                    reasoning.append(f"⚾ **先發投手優勢**：主隊先發 {home_p} (ERA {home_p_era:.2f}) 近期表現優於客隊 {away_p} (ERA {away_p_era:.2f})。")
                else:
                    reasoning.append(f"⚾ **先發投手優勢**：客隊先發 {away_p} (ERA {away_p_era:.2f}) 近期表現優於主隊 {home_p} (ERA {home_p_era:.2f})。")

                if home_ops > away_ops:
                    reasoning.append(f"🏏 **打線破壞力**：主隊打線整體 OPS ({home_ops:.3f}) 領先客隊 ({away_ops:.3f})，具備較佳的得分期望值。")
                else:
                    reasoning.append(f"🏏 **打線破壞力**：客隊打線整體 OPS ({away_ops:.3f}) 領先主隊 ({home_ops:.3f})，具備較佳的得分期望值。")

                reasoning.append(f"🛡️ **牛棚戰力與疲勞度**：主隊牛棚 ERA {home_bp_era:.2f} (近兩日消耗 {home_bp_pitches} 球) vs 客隊牛棚 ERA {away_bp_era:.2f} (近兩日消耗 {away_bp_pitches} 球)。")
                if home_bp_pitches > 80:
                    reasoning.append(f"⚠️ <span style='color:#FF4444;'>**疲勞警告**</span>：主隊 {home_t} 牛棚近期消耗巨大，可能影響比賽後半段壓制力！")
                if away_bp_pitches > 80:
                    reasoning.append(f"⚠️ <span style='color:#FF4444;'>**疲勞警告**</span>：客隊 {away_t} 牛棚近期消耗巨大，可能影響比賽後半段壓制力！")

                reasoning.append(f"🏟️ **綜合勝率評估**：結合投打實力與牛棚疲勞度，推算出的最終期望勝率。")
                
                with st.expander("🧠 點擊查看 AI 勝率預測邏輯", expanded=True):
                    for r in reasoning:
                        st.markdown(f"<div style='font-size:{int(st.session_state.font_size * 1.5)}px; margin-bottom:10px;'>{r}</div>", unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown(f"<h3 style='color:{home_t_color}'>⚔️ 上半局：{away_t} (客隊打線) VS {home_p} (主隊先發)</h3>", unsafe_allow_html=True)
                if not hp_stats.empty:
                    st.markdown(f"<div class='table-scroll-container'>{hp_stats.drop(columns=['Player_ID']).style.format(precision=3).hide(axis='index').to_html()}</div>", unsafe_allow_html=True)
                else: st.warning(f"查無主隊先發 {home_p} 的本季數據")
                    
                ah_stats = ah_stats.sort_values(by='OPS', ascending=False)
                if home_p_id and not ah_stats.empty:
                    bvp_df = fetch_bvp_data(home_p_id, ah_stats['Player_ID'].tolist())
                    if not bvp_df.empty:
                        st.markdown(f"<div style='font-size:{int(st.session_state.font_size * 1.5)}px; font-weight:bold; margin-top:10px; margin-bottom:10px;'>🔥 生涯對戰紀錄 (BvP)</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='table-scroll-container'>{bvp_df.style.format(precision=3).hide(axis='index').to_html()}</div>", unsafe_allow_html=True)
                if not ah_stats.empty:
                    st.markdown(f"<div style='font-size:{int(st.session_state.font_size * 1.5)}px; font-weight:bold; margin-top:10px; margin-bottom:10px;'>**客隊打線本季表現**</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='table-scroll-container'>{ah_stats.drop(columns=['Player_ID']).style.format(precision=3).hide(axis='index').to_html()}</div>", unsafe_allow_html=True)
                
                st.divider()
                st.markdown(f"<h3 style='color:{away_t_color}'>⚔️ 下半局：{home_t} (主隊打線) VS {away_p} (客隊先發)</h3>", unsafe_allow_html=True)
                if not ap_stats.empty:
                    st.markdown(f"<div class='table-scroll-container'>{ap_stats.drop(columns=['Player_ID']).style.format(precision=3).hide(axis='index').to_html()}</div>", unsafe_allow_html=True)
                else: st.warning(f"查無客隊先發 {away_p} 的本季數據")
                    
                hh_stats = hh_stats.sort_values(by='OPS', ascending=False)
                if away_p_id and not hh_stats.empty:
                    bvp_df = fetch_bvp_data(away_p_id, hh_stats['Player_ID'].tolist())
                    if not bvp_df.empty:
                        st.markdown(f"<div style='font-size:{int(st.session_state.font_size * 1.5)}px; font-weight:bold; margin-top:10px; margin-bottom:10px;'>🔥 生涯對戰紀錄 (BvP)</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='table-scroll-container'>{bvp_df.style.format(precision=3).hide(axis='index').to_html()}</div>", unsafe_allow_html=True)
                if not hh_stats.empty:
                    st.markdown(f"<div style='font-size:{int(st.session_state.font_size * 1.5)}px; font-weight:bold; margin-top:10px; margin-bottom:10px;'>**主隊打線本季表現**</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='table-scroll-container'>{hh_stats.drop(columns=['Player_ID']).style.format(precision=3).hide(axis='index').to_html()}</div>", unsafe_allow_html=True)

    with tab_mvp:
        st.subheader(f"👑 {year} 賽季 MVP 預測排行榜")
        st.caption("透過綜合 WAR 與核心進階數據，計算出的 MVP 指數排行榜")
        with st.spinner("運算 MVP 積分中..."):
            mvp_df = data.copy()
            if not mvp_df.empty:
                if p_type == '打者':
                    mvp_df['MVP_Index'] = (mvp_df['WAR'] * 20 + mvp_df['OPS'] * 50 + mvp_df['wRC+'] * 0.5).round(1)
                    keep_cols = ['Player', 'Team', 'Position', 'WAR', 'OPS', 'wRC+', 'HR', 'MVP_Index']
                else:
                    mvp_df['MVP_Index'] = (mvp_df['WAR'] * 25 + mvp_df['K%'] * 1.5 - mvp_df['ERA'] * 10).round(1)
                    keep_cols = ['Player', 'Team', 'Position', 'WAR', 'ERA', 'WHIP', 'K%', 'MVP_Index']
                    
                mvp_top = mvp_df.sort_values('MVP_Index', ascending=False).head(15).reset_index(drop=True)
                mvp_top.index += 1
                mvp_style = mvp_top[keep_cols].style.format(precision=2).background_gradient(subset=['MVP_Index'], cmap='YlOrRd')
                st.markdown(f"<div class='table-scroll-container'>{mvp_style.to_html()}</div>", unsafe_allow_html=True)
    
    if p_type == "投手" and tab_cy is not None:
        with tab_cy:
            st.subheader(f"🏆 {year} 賽季 賽揚獎 (Cy Young) 預測排行榜")
            st.caption("透過綜合 WAR、K%、ERA 與 WHIP 計算出的賽揚指數進行大數據預測")
            with st.spinner("運算賽揚積分中..."):
                cy_df = data.copy()
                if not cy_df.empty:
                    cy_df['Cy_Index'] = (cy_df['WAR'] * 15 + cy_df['K%'] * 1.2 - cy_df['ERA'] * 8 - cy_df['WHIP'] * 10).round(1)
                    cy_top = cy_df.sort_values('Cy_Index', ascending=False).head(15).reset_index(drop=True)
                    cy_top.index += 1
                    cy_style = cy_top[['Player', 'Team', 'Position', 'WAR', 'ERA', 'WHIP', 'K%', 'IP', 'Cy_Index']].style.format(precision=2).background_gradient(subset=['Cy_Index'], cmap='Blues')
                    st.markdown(f"<div class='table-scroll-container'>{cy_style.to_html()}</div>", unsafe_allow_html=True)

    with tab_milb:
        st.subheader(f"🌱 小聯盟潛力 {p_type} 農場新秀報告 (MiLB Top Prospects)")
        st.caption("即時追蹤小聯盟農場的大物新秀表現，並限制每支球隊最多顯示 20 名菁英。")
        
        lvl_map = {"AAA (3A)": 11, "AA (2A)": 12, "High-A": 13, "Single-A": 14}
        milb_level = st.selectbox("選擇小聯盟層級", list(lvl_map.keys()))
        
        with st.spinner(f"撈取 {milb_level} {p_type} 數據中..."):
            milb_df = fetch_milb_stats(year, lvl_map[milb_level], p_type)
            if not milb_df.empty:
                milb_teams = sorted(milb_df['大聯盟母隊 (MLB Team)'].unique())
                col_t, col_s, col_o = st.columns([1, 1, 1])
                sel_team = col_t.selectbox("選擇大聯盟母隊", ["全聯盟"] + milb_teams)
                
                sort_cols = [c for c in milb_df.columns if c not in ['球員 (Player)', '大聯盟母隊 (MLB Team)']]
                
                def_idx = 0
                if p_type == '打者' and 'OPS' in sort_cols: def_idx = sort_cols.index('OPS')
                if p_type == '投手' and 'ERA' in sort_cols: def_idx = sort_cols.index('ERA')
                    
                sel_sort = col_s.selectbox("自訂排序指標", sort_cols, index=def_idx)
                
                lower_is_better_milb = ['ERA', 'WHIP', 'L'] if p_type == '投手' else []
                def_order_milb = 1 if sel_sort in lower_is_better_milb else 0
                sel_order = col_o.radio("排序方式 ", ["由高到低", "由低到高"], index=def_order_milb, horizontal=True)
                
                if sel_team != "全聯盟": milb_df = milb_df[milb_df['大聯盟母隊 (MLB Team)'] == sel_team]
                
                asc = True if sel_order == "由低到高" else False
                
                milb_df = milb_df.sort_values(by=sel_sort, ascending=asc).head(20).reset_index(drop=True)
                milb_df.index += 1
                
                cmap = 'Greens' if p_type == '打者' else 'Blues'
                if sel_sort in lower_is_better_milb: cmap = 'Blues_r' if p_type == '投手' else 'Greens_r'
                
                milb_style = milb_df.style.format(precision=3).background_gradient(subset=[sel_sort], cmap=cmap)
                st.markdown(f"<div class='table-scroll-container'>{milb_style.to_html()}</div>", unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ 目前查無 {year} 賽季 {milb_level} 的 {p_type} 數據。\n\n可能原因：小聯盟賽季尚未開始（通常為 4 月初），或該層級暫無符合篩選條件的球員。")