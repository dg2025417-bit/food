import streamlit as st
import requests
import re
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="급식메뉴찾기", page_icon="🍱", layout="wide")
st.title("🍱 급식메뉴찾기")
st.write("최대 3개의 학교 급식을 비교해보세요!")

API_KEY = st.secrets.get("NEIS_API_KEY", "")

# ---------------------------
# 세션 상태 초기화 (학교 3개 슬롯)
# ---------------------------
for i in range(1, 4):
    if f"school_list_{i}" not in st.session_state:
        st.session_state[f"school_list_{i}"] = []
    if f"selected_school_{i}" not in st.session_state:
        st.session_state[f"selected_school_{i}"] = None


# ---------------------------
# 학교 검색 함수
# ---------------------------
def search_school(school_name):
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {"Type": "json", "SCHUL_NM": school_name}
    if API_KEY:
        params["KEY"] = API_KEY

    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
    except Exception as e:
        st.error(f"학교 검색 중 오류가 발생했어요: {e}")
        return []

    if "schoolInfo" not in data:
        return []

    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError):
        return []

    return [
        {
            "학교명": row.get("SCHUL_NM"),
            "교육청코드": row.get("ATPT_OFCDC_SC_CODE"),
            "학교코드": row.get("SD_SCHUL_CODE"),
            "지역": row.get("LCTN_SC_NM"),
        }
        for row in rows
    ]


# ---------------------------
# 급식 메뉴 검색 함수
# ---------------------------
def search_meal(office_code, school_code, from_date, to_date):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": from_date,
        "MLSV_TO_YMD": to_date,
    }
    if API_KEY:
        params["KEY"] = API_KEY

    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
    except Exception as e:
        st.error(f"급식 정보를 불러오는 중 오류가 발생했어요: {e}")
        return []

    if "mealServiceDietInfo" not in data:
        return []

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError):
        return []

    meals = []
    for row in rows:
        raw_menu = row.get("DDISH_NM", "")
        menu_items = raw_menu.split("<br/>")
        clean_items = [re.sub(r"\([\d.]+\)", "", item).strip() for item in menu_items]
        clean_items = [item for item in clean_items if item]

        cal_raw = row.get("CAL_INFO", "")
        cal_match = re.search(r"[\d.]+", cal_raw)
        cal_value = float(cal_match.group()) if cal_match else None

        meals.append({
            "날짜": row.get("MLSV_YMD"),
            "메뉴": clean_items,
            "메뉴_개수": len(clean_items),
            "칼로리": cal_raw,
            "칼로리_숫자": cal_value,
        })
    return meals


def format_date(ymd):
    y, m, d = ymd[:4], ymd[4:6], ymd[6:8]
    return f"{y}년 {m}월 {d}일"


# ---------------------------
# 학교 검색 + 선택 UI (재사용 가능한 함수)
# ---------------------------
def school_selector(slot_num):
    st.markdown(f"#### 🏫 학교 {slot_num}")
    school_input = st.text_input(
        f"학교 이름 입력 (학교 {slot_num})",
        key=f"input_{slot_num}",
        placeholder="예: 당곡",
    )

    if st.button(f"검색하기", key=f"search_btn_{slot_num}"):
        if school_input.strip() == "":
            st.warning("학교 이름을 입력해주세요.")
        else:
            with st.spinner("검색 중..."):
                result = search_school(school_input.strip())
            if not result:
                st.error("검색된 학교가 없어요.")
                st.session_state[f"school_list_{slot_num}"] = []
            else:
                st.session_state[f"school_list_{slot_num}"] = result

    school_list = st.session_state[f"school_list_{slot_num}"]
    if school_list:
        options = [f"{s['학교명']} ({s['지역']})" for s in school_list]
        idx = st.selectbox(
            "학교 선택",
            range(len(options)),
            format_func=lambda i: options[i],
            key=f"select_{slot_num}",
        )
        st.session_state[f"selected_school_{slot_num}"] = school_list[idx]
        st.success(f"선택됨: {school_list[idx]['학교명']}")


# ---------------------------
# 1단계: 학교 3개 검색 및 선택
# ---------------------------
st.subheader("1️⃣ 비교할 학교 선택 (최대 3개)")

col1, col2, col3 = st.columns(3)
with col1:
    school_selector(1)
with col2:
    school_selector(2)
with col3:
    school_selector(3)

# ---------------------------
# 2단계: 조회 기간 선택
# ---------------------------
selected_schools = [
    st.session_state[f"selected_school_{i}"] for i in range(1, 4)
    if st.session_state[f"selected_school_{i}"] is not None
]

if selected_schools:
    st.subheader("2️⃣ 급식 조회 기간 선택")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("조회 시작일", value=date.today())
    with col2:
        end_date = st.date_input("조회 종료일", value=date.today() + timedelta(days=6))

    if st.button("🔍 급식 비교하기"):
        if start_date > end_date:
            st.warning("시작일이 종료일보다 늦을 수 없어요.")
        else:
            from_ymd = start_date.strftime("%Y%m%d")
            to_ymd = end_date.strftime("%Y%m%d")

            school_meal_data = {}  # 학교명 -> meals 리스트

            with st.spinner("급식 정보를 불러오고 있어요..."):
                for school in selected_schools:
                    meals = search_meal(
                        school["교육청코드"], school["학교코드"], from_ymd, to_ymd
                    )
                    school_meal_data[school["학교명"]] = meals

            # ---------------------------
            # 학교별 급식 메뉴 목록
            # ---------------------------
            st.subheader("🍽 학교별 급식 메뉴")
            cols = st.columns(len(school_meal_data))
            for idx, (school_name, meals) in enumerate(school_meal_data.items()):
                with cols[idx]:
                    st.markdown(f"### 🏫 {school_name}")
                    if not meals:
                        st.info("해당 기간 급식 정보가 없어요.")
                        continue
                    for meal in meals:
                        st.markdown(f"**📅 {format_date(meal['날짜'])}**")
                        for item in meal["메뉴"]:
                            st.write(f"- {item}")
                        st.caption(f"칼로리: {meal['칼로리']} · 메뉴 {meal['메뉴_개수']}개")
                        st.divider()

            # ---------------------------
            # 학교별 대표 날짜(칼로리 최고 / 메뉴 최소 / 메뉴 최다) 하나씩 뽑기
            # ---------------------------
            st.subheader("🏆 학교별 대표 급식 (각 주제당 날짜 1개씩)")

            summary = {}  # 학교명 -> {"최고칼로리": meal, "최소메뉴": meal, "최다메뉴": meal}

            for school_name, meals in school_meal_data.items():
                meals_with_cal = [m for m in meals if m["칼로리_숫자"] is not None]
                meals_with_menu = [m for m in meals if m["메뉴_개수"] > 0]

                if meals_with_cal and meals_with_menu:
                    summary[school_name] = {
                        "최고칼로리": max(meals_with_cal, key=lambda m: m["칼로리_숫자"]),
                        "최소메뉴": min(meals_with_menu, key=lambda m: m["메뉴_개수"]),
                        "최다메뉴": max(meals_with_menu, key=lambda m: m["메뉴_개수"]),
                    }

            if summary:
                tab1, tab2, tab3 = st.tabs(["🔥 칼로리 최고", "📉 메뉴 최소", "📈 메뉴 최다"])

                # --- 탭 1: 칼로리 최고 ---
                with tab1:
                    cols = st.columns(len(summary))
                    for idx, (school_name, info) in enumerate(summary.items()):
                        meal = info["최고칼로리"]
                        with cols[idx]:
                            st.markdown(f"#### 🏫 {school_name}")
                            st.write(f"**{format_date(meal['날짜'])}**")
                            for item in meal["메뉴"]:
                                st.write(f"- {item}")
                            st.caption(f"칼로리: {meal['칼로리']}")

                    # 비교 막대그래프
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=list(summary.keys()),
                        y=[info["최고칼로리"]["칼로리_숫자"] for info in summary.values()],
                        text=[f"{info['최고칼로리']['칼로리_숫자']:.0f}" for info in summary.values()],
                        textposition="outside",
                        marker_color="crimson",
                    ))
                    fig.update_layout(
                        title="학교별 최고 칼로리 비교",
                        xaxis_title="학교",
                        yaxis_title="칼로리 (Kcal)",
                        template="plotly_white",
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # --- 탭 2: 메뉴 최소 ---
                with tab2:
                    cols = st.columns(len(summary))
                    for idx, (school_name, info) in enumerate(summary.items()):
                        meal = info["최소메뉴"]
                        with cols[idx]:
                            st.markdown(f"#### 🏫 {school_name}")
                            st.write(f"**{format_date(meal['날짜'])}**")
                            for item in meal["메뉴"]:
                                st.write(f"- {item}")
                            st.caption(f"메뉴 가짓수: {meal['메뉴_개수']}개")

                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=list(summary.keys()),
                        y=[info["최소메뉴"]["메뉴_개수"] for info in summary.values()],
                        text=[info["최소메뉴"]["메뉴_개수"] for info in summary.values()],
                        textposition="outside",
                        marker_color="orange",
                    ))
                    fig.update_layout(
                        title="학교별 최소 메뉴 가짓수 비교",
                        xaxis_title="학교",
                        yaxis_title="메뉴 가짓수 (개)",
                        template="plotly_white",
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # --- 탭 3: 메뉴 최다 ---
                with tab3:
                    cols = st.columns(len(summary))
                    for idx, (school_name, info) in enumerate(summary.items()):
                        meal = info["최다메뉴"]
                        with cols[idx]:
                            st.markdown(f"#### 🏫 {school_name}")
                            st.write(f"**{format_date(meal['날짜'])}**")
                            for item in meal["메뉴"]:
                                st.write(f"- {item}")
                            st.caption(f"메뉴 가짓수: {meal['메뉴_개수']}개")

                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=list(summary.keys()),
                        y=[info["최다메뉴"]["메뉴_개수"] for info in summary.values()],
                        text=[info["최다메뉴"]["메뉴_개수"] for info in summary.values()],
                        textposition="outside",
                        marker_color="seagreen",
                    ))
                    fig.update_layout(
                        title="학교별 최다 메뉴 가짓수 비교",
                        xaxis_title="학교",
                        yaxis_title="메뉴 가짓수 (개)",
                        template="plotly_white",
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("비교할 만한 급식 데이터가 충분하지 않아요.")
else:
    st.info("먼저 위에서 학교를 1개 이상 검색하고 선택해주세요.")
