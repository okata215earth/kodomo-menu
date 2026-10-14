import random
import json
import zoneinfo
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# 1. ページ基本設定 & タイムゾーン設定
# --------------------------------------------------
st.set_page_config(
    page_title="愛怜の毎日献立表",
    page_icon="🍳",
    layout="centered"
)

JST = zoneinfo.ZoneInfo("Asia/Tokyo")
today_date = pd.Timestamp.now(JST).date()

# --------------------------------------------------
# カスタムCSS（スマホフレンドリーな温かみのあるデザイン）
# --------------------------------------------------
st.markdown("""
<style>
    .main {
        background-color: #FDFCFB;
        font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif;
        color: #554848;
    }
    .menu-title-container {
        text-align: center;
        padding: 10px 0 15px 0;
        margin-bottom: 15px;
    }
    .menu-title {
        color: #E67E22;
        font-size: 1.5rem;
        font-weight: bold;
        letter-spacing: 0.5px;
    }
    .menu-subtitle {
        color: #9E8B8B;
        font-size: 0.8rem;
        margin-top: 2px;
    }
    .menu-card {
        background-color: #FFFFFF;
        border-radius: 20px;
        padding: 16px 14px;
        margin-bottom: 16px;
        box-shadow: 0 4px 14px rgba(230, 126, 34, 0.08);
        border: 1px solid #FAD7A0;
    }
    .menu-card-main {
        background: linear-gradient(135deg, #FEF9E7 0%, #FCF3CF 100%);
        border-radius: 16px;
        padding: 14px;
        margin-bottom: 10px;
        border: 1px solid #F9E79F;
    }
    .menu-card-sub {
        background-color: #F4F6F6;
        border-radius: 16px;
        padding: 12px;
        margin-bottom: 8px;
        border: 1px solid #E5E7E9;
    }
    .menu-header {
        font-size: 1.0rem;
        font-weight: bold;
        color: #D35400;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .stButton > button {
        border-radius: 25px !important;
        background: linear-gradient(135deg, #F39C12 0%, #E67E22 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        font-size: 0.9rem !important;
        padding: 8px 12px !important;
        box-shadow: 0 4px 12px rgba(230, 126, 34, 0.2) !important;
        width: 100%;
    }
    div[data-baseweb="input"], div[data-baseweb="select"] {
        border-radius: 14px !important;
        border-color: #FAD7A0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ヘッダー
st.markdown("""
<div class="menu-title-container">
    <div class="menu-title">🍳 幼児の毎日献立表（夜）</div>
    <div class="menu-subtitle">今日のごはん、何にする？迷ったらガチャ！</div>
</div>
""", unsafe_allow_html=True)

# --------------------------------------------------
# 2. Googleスプレッドシート接続＆レシピデータ管理
# --------------------------------------------------
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    info = json.loads(st.secrets["gcp_service_account"]["json_text"])
    credentials = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(credentials)


def get_recipe_worksheet():
    gc = get_gspread_client()
    spreadsheet_name = st.secrets["spreadsheet"]["spreadsheet_name"]
    sh = gc.open(spreadsheet_name)
    try:
        ws = sh.worksheet("recipes")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="recipes", rows=100, cols=3)
        ws.append_row(["recipe_name", "category", "memo"])
    return ws


@st.cache_data(ttl=60)
def fetch_recipes_from_sheet():
    try:
        ws = get_recipe_worksheet()
        values = ws.get_all_values()
        
        # 値が空、またはヘッダー行すらない場合は自動で初期化
        if not values or len(values) == 0:
            ws.append_row(["recipe_name", "category", "memo"])
            return pd.DataFrame(columns=["recipe_name", "category", "memo"])
        
        # 1行目がヘッダーでない場合（データのみが入っているなど）の対策
        header = values[0]
        if "recipe_name" not in header:
            ws.insert_row(["recipe_name", "category", "memo"], index=1)
            values = ws.get_all_values()
            
        if len(values) <= 1:
            return pd.DataFrame(columns=["recipe_name", "category", "memo"])
        
        df = pd.DataFrame(values[1:], columns=values[0])
        # 必要なカラムが確実に存在するように保証
        for col in ["recipe_name", "category", "memo"]:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception as e:
        # レスポンス200エラーなどの例外をキャッチした場合は空のDFを返しつつ警告を表示
        return pd.DataFrame(columns=["recipe_name", "category", "memo"])


def load_recipes():
    if "df_recipes" not in st.session_state:
        st.session_state["df_recipes"] = fetch_recipes_from_sheet()
    return st.session_state["df_recipes"]


def append_recipe(recipe_name, category, memo):
    try:
        ws = get_recipe_worksheet()
        ws.append_row([recipe_name, category, memo])
        
        new_df = pd.DataFrame([[recipe_name, category, memo]], columns=["recipe_name", "category", "memo"])
        st.session_state["df_recipes"] = pd.concat([st.session_state["df_recipes"], new_df], ignore_index=True)
        fetch_recipes_from_sheet.clear()
    except Exception as e:
        st.error(f"レシピ登録エラー: {e}")


def delete_recipe(recipe_name, category):
    try:
        ws = get_recipe_worksheet()
        records = ws.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row.get("recipe_name")) == str(recipe_name) and str(row.get("category")) == str(category):
                ws.delete_rows(idx)
                fetch_recipes_from_sheet.clear()
                st.session_state["df_recipes"] = fetch_recipes_from_sheet()
                break
    except Exception as e:
        st.error(f"レシピ削除エラー: {e}")


# --------------------------------------------------
# 3. タブによる機能切り替え
# --------------------------------------------------
tab1, tab2, tab3 = st.tabs(["✨ 今日の献立", "📝 レシピ登録", "📚 レシピ一覧"])

df_recipes = load_recipes()

# --- タブ1：今日の献立提案（ランダムガチャ） ---
with tab1:
    st.markdown('<div class="menu-card">', unsafe_allow_html=True)
    st.markdown('<div class="menu-header">🎲 本日の夜ごはん献立ガチャ</div>', unsafe_allow_html=True)
    st.write("ボタンを押すと、主菜1つと副菜・汁物2つをランダムに組み合わせます！")

    if st.button("🍳 本日の献立を決める！"):
            main_dishes = df_recipes[df_recipes["category"] == "主菜"]
            sub_dishes = df_recipes[df_recipes["category"] == "副菜・汁物"]

            if len(main_dishes) < 1 or len(sub_dishes) < 2:
                st.warning("⚠️ ガチャを回すには「主菜」を1つ以上、「副菜・汁物」を2つ以上登録してください！")
            else:
                # 主菜を1つ選出
                selected_main = main_dishes.sample(n=1).iloc[0]

                # 副菜・汁物の中から「お味噌汁（みそ汁）」が含まれるものを分離
                # （レシピ名またはメモに「味噌汁」または「みそ汁」が含まれるものを判定）
                is_miso = lambda row: "味噌汁" in str(row["recipe_name"]) or "みそ汁" in str(row["recipe_name"]) or "味噌汁" in str(row["memo"]) or "みそ汁" in str(row["memo"])
                
                miso_dishes = sub_dishes[sub_dishes.apply(is_miso, axis=1)]
                other_sub_dishes = sub_dishes[~sub_dishes.apply(is_miso, axis=1)]

                selected_sub1 = None
                selected_sub2 = None

                # お味噌汁系レシピが1つ以上ある場合、最大1つに制限する
                if not miso_dishes.empty and len(sub_dishes) >= 2:
                    # 50%の確率でお味噌汁を1つ枠に組み込む、またはお味噌汁を必ず1枠に入れるなどの調整が可能ですが、
                    # ここでは「お味噌汁系から最大1つ、その他から残りの枠を選ぶ」安全なロジックにします
                    
                    # パターンA: お味噌汁を1つ含める場合
                    chosen_miso = miso_dishes.sample(n=1).iloc[0]
                    
                    # 残り1枠を「お味噌汁以外」から選ぶ（もしお味噌汁以外が足りない場合は例外処理）
                    pool_for_remaining = pd.concat([other_sub_dishes, miso_dishes.drop(chosen_miso.name)]).drop_duplicates()
                    
                    if not pool_for_remaining.empty:
                        chosen_other = pool_for_remaining.sample(n=1).iloc[0]
                        # ランダムに順番をシャッフル
                        subs_list = [chosen_miso, chosen_other]
                        random.shuffle(subs_list)
                        selected_sub1 = subs_list[0]
                        selected_sub2 = subs_list[1]
                    else:
                        # プールが足りない場合は通常ランダム
                        selected_subs = sub_dishes.sample(n=2).reset_index(drop=True)
                        selected_sub1 = selected_subs.iloc[0]
                        selected_sub2 = selected_subs.iloc[1]
                else:
                    # お味噌汁系がない、または条件に満たない場合は通常のランダム2つ
                    selected_subs = sub_dishes.sample(n=2).reset_index(drop=True)
                    selected_sub1 = selected_subs.iloc[0]
                    selected_sub2 = selected_subs.iloc[1]

                st.session_state["today_menu"] = {
                    "main": selected_main,
                    "sub1": selected_sub1,
                    "sub2": selected_sub2
                }

    if "today_menu" in st.session_state:
        menu = st.session_state["today_menu"]
        
        st.markdown("---")
        st.markdown("### 🌟 本日の献立提案")
        
        m = menu["main"]
        st.markdown(f"""
        <div class="menu-card-main">
            <div style="font-size:0.75rem; font-weight:bold; color:#D35400;">🥇 主菜（メイン）</div>
            <div style="font-size:1.1rem; font-weight:bold; color:#2C3E50; margin-top:2px;">{m['recipe_name']}</div>
            <div style="font-size:0.8rem; color:#7F8C8D; margin-top:2px;">💬 メモ: {m['memo'] if m['memo'] else 'なし'}</div>
        </div>
        """, unsafe_allow_html=True)

        s1 = menu["sub1"]
        st.markdown(f"""
        <div class="menu-card-sub">
            <div style="font-size:0.75rem; font-weight:bold; color:#7F8C8D;">🥈 副菜・汁物 ①</div>
            <div style="font-size:1.0rem; font-weight:bold; color:#2C3E50; margin-top:2px;">{s1['recipe_name']}</div>
            <div style="font-size:0.8rem; color:#7F8C8D; margin-top:2px;">💬 メモ: {s1['memo'] if s1['memo'] else 'なし'}</div>
        </div>
        """, unsafe_allow_html=True)

        s2 = menu["sub2"]
        st.markdown(f"""
        <div class="menu-card-sub">
            <div style="font-size:0.75rem; font-weight:bold; color:#7F8C8D;">🥉 副菜・汁物 ②</div>
            <div style="font-size:1.0rem; font-weight:bold; color:#2C3E50; margin-top:2px;">{s2['recipe_name']}</div>
            <div style="font-size:0.8rem; color:#7F8C8D; margin-top:2px;">💬 メモ: {s2['memo'] if s2['memo'] else 'なし'}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# --- タブ2：レシピ登録 ---
with tab2:
    st.markdown('<div class="menu-card">', unsafe_allow_html=True)
    st.markdown('<div class="menu-header">📝 新しいレシピを登録する</div>', unsafe_allow_html=True)

    with st.form("recipe_form", clear_on_submit=True):
        recipe_name = st.text_input("レシピ名・メニュー名", placeholder="例：豆腐ハンバーグ、ほうれん草のおひたし")
        category = st.selectbox("分類", options=["主菜", "副菜・汁物"])
        memo = st.text_input("メモ（食材や子どもウケなど）", placeholder="例：細かく刻むとよく食べる")
        
        submitted = st.form_submit_button("✨ レシピを登録する")
        
        if submitted:
            if recipe_name.strip() == "":
                st.error("レシピ名を入力してください。")
            else:
                append_recipe(recipe_name.strip(), category, memo.strip())
                st.success(f"「{recipe_name}」を登録しました！ 🎉")

    st.markdown('</div>', unsafe_allow_html=True)


# --- タブ3：レシピ一覧＆削除 ---
with tab3:
    st.markdown('<div class="menu-card">', unsafe_allow_html=True)
    st.markdown('<div class="menu-header">📚 登録済みレシピ一覧</div>', unsafe_allow_html=True)

    if df_recipes.empty:
        st.info("登録されているレシピはまだありません。「レシピ登録」タブから追加してください。")
    else:
        filter_cat = st.radio("絞り込み", options=["すべて", "主菜", "副菜・汁物"], horizontal=True)
        
        display_df = df_recipes if filter_cat == "すべて" else df_recipes[df_recipes["category"] == filter_cat]
        
        st.write(f"全 {len(display_df)} 件のレシピ")
        
        for idx, row in display_df.iterrows():
            col_info, col_del = st.columns([8, 2])
            with col_info:
                badge_color = "#E67E22" if row["category"] == "主菜" else "#7F8C8D"
                st.markdown(f"""
                <div style="padding: 6px 0; border-bottom: 1px solid #FAD7A0;">
                    <span style="background-color: {badge_color}; color: white; padding: 2px 6px; border-radius: 6px; font-size: 0.75rem;">{row['category']}</span>
                    <strong style="margin-left: 6px; font-size: 0.95rem;">{row['recipe_name']}</strong><br>
                    <span style="font-size: 0.8rem; color: #7F8C8D; margin-left: 4px;">💬 {row['memo'] if row['memo'] else 'メモなし'}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_del:
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                if st.button("🗑️ 削除", key=f"del_rec_{idx}"):
                    delete_recipe(row["recipe_name"], row["category"])
                    st.toast(f"「{row['recipe_name']}」を削除しました")
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
